"""Композитор эмодзи-паков.

Полотно 800×2500 = сетка 8×25 ячеек по 100×100 (8 колонок — как в панели эмодзи Telegram).
Элементы раскладываются по ячейкам:
  single  — одиночное эмодзи 1×1
  big     — крупный арт из нескольких эмодзи (например 4×4, 8×5)
  banner  — баннер 2–4 (до 8) в ширину × 1 в высоту, можно с текстом
  tall    — вертикальный разделитель 1×2+ (коллаж/полоса)
  collage — коллаж из нескольких картинок в одном блоке
  heart   — картинка в форме сердечка/рамочка «стирающая» центр, ч/б — отдельная плашка
  text    — текстовый баннер без картинки
  spacer  — пустое (прозрачное) место
После рендера полотно режется на эмодзи 100×100 построчно, порядок = порядок в паке.
"""
from __future__ import annotations

import json
import math
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from .. import rules
from ..ai.providers import AIClient
from ..config import UPLOAD_DIR
from ..imageutil import (apply_shape, border_stats, draw_text_block, fit, gradient, is_animated, load_frames,
                         remove_background, rounded, saliency_focus, to_bw, trim_transparent)
from . import convert

CELL = 100
COLS = 8
ROWS = 25
KINDS = ["single", "big", "banner", "tall", "collage", "heart", "text", "spacer"]


# ---------------- анализ ----------------
def analyze(path: str | Path) -> dict:
    path = Path(path)
    frames, durs = load_frames(path, max_frames=2)
    im = frames[0]
    w, h = im.size
    aspect = w / h
    edge_color, spread, transparency = border_stats(im)
    gray = im.convert("L").resize((64, 64))
    hist = gray.histogram()
    entropy = -sum((c / 4096) * math.log2(c / 4096) for c in hist if c)
    has_alpha = transparency > 0.04
    uniform_bg = spread < 0.07
    anim = is_animated(path)
    info = {"file": path.name, "w": w, "h": h, "aspect": round(aspect, 3), "has_alpha": has_alpha,
            "uniform_bg": uniform_bg, "edge_color": "#%02x%02x%02x" % edge_color, "entropy": round(entropy, 2),
            "animated": anim}
    info["suggest"] = suggest(info)
    return info


def suggest(info: dict) -> dict:
    """Эвристика «что сделать с картинкой» (если ИИ отключён или как подсказка ему)."""
    a = info["aspect"]
    remove_bg = (info["uniform_bg"] or info["has_alpha"]) and not (a > 1.8 or a < 0.55)
    if a >= 1.8:
        w = 4 if a >= 3.4 else 3 if a >= 2.5 else 2
        return {"kind": "banner", "w": w, "h": 1, "remove_bg": False, "fit": "cover"}
    if a <= 0.55:
        h = 4 if a <= 0.3 else 3 if a <= 0.42 else 2
        return {"kind": "tall", "w": 1, "h": h, "remove_bg": False, "fit": "cover"}
    detailed = info["entropy"] > 6.6 and min(info["w"], info["h"]) >= 300
    if remove_bg and info["entropy"] < 5.8:
        return {"kind": "single", "w": 1, "h": 1, "remove_bg": True, "fit": "contain"}
    if detailed:
        size = 4 if info["entropy"] > 7.2 else 3
        return {"kind": "big", "w": max(1, round(size * min(a, 2))), "h": size, "remove_bg": remove_bg,
                "fit": "contain" if remove_bg else "cover"}
    return {"kind": "single", "w": 1, "h": 1, "remove_bg": remove_bg, "fit": "contain" if remove_bg else "cover"}


# ---------------- раскладка ----------------
def _free(grid, x, y, w, h, cols, rows):
    if x + w > cols or y + h > rows:
        return False
    return all(not grid[yy][xx] for yy in range(y, y + h) for xx in range(x, x + w))


def _occupy(grid, x, y, w, h):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            grid[yy][xx] = True


def pack(items: list[dict], cols: int = COLS, rows: int = ROWS, center_big: bool = True,
         keep_fixed: bool = True) -> list[dict]:
    """Расставляет элементы по сетке. Элементы с locked=True не двигаются."""
    grid = [[False] * cols for _ in range(rows)]
    placed = []
    for it in items:
        if keep_fixed and it.get("locked") and "x" in it:
            _occupy(grid, it["x"], it["y"], it["w"], it["h"])
    for it in items:
        if keep_fixed and it.get("locked") and "x" in it:
            placed.append(it)
            continue
        it["w"] = max(1, min(cols, int(it.get("w", 1))))
        it["h"] = max(1, min(rows, int(it.get("h", 1))))
        done = False
        for y in range(rows):
            xs = list(range(cols - it["w"] + 1))
            if center_big and it["w"] >= 3 and it.get("kind") in ("big", "banner", "text", "collage"):
                c = (cols - it["w"]) // 2
                xs.sort(key=lambda x: abs(x - c))
            for x in xs:
                if _free(grid, x, y, it["w"], it["h"], cols, rows):
                    it["x"], it["y"] = x, y
                    _occupy(grid, x, y, it["w"], it["h"])
                    done = True
                    break
            if done:
                break
        it["overflow"] = not done
        placed.append(it)
    return placed


def auto_layout(files: list[str], cols: int = COLS, rows: int = ROWS, style: str = "balanced") -> list[dict]:
    items = []
    for f in files:
        info = analyze(UPLOAD_DIR / f)
        s = info["suggest"]
        items.append({"id": f"it{len(items)}", "src": f, "kind": s["kind"], "w": s["w"], "h": s["h"],
                      "remove_bg": s["remove_bg"], "fit": s["fit"], "emoji": "✨", "analysis": info})
    items = [rules.apply_emoji_item(it) for it in items]
    if style == "big_first":
        items.sort(key=lambda it: -(it["w"] * it["h"]))
    elif style == "rows":  # крупные блоки, между ними ряды одиночных
        big = [i for i in items if i["w"] * i["h"] > 1]
        small = [i for i in items if i["w"] * i["h"] == 1]
        items = []
        while big or small:
            if big:
                items.append(big.pop(0))
            items.extend(small[:cols])
            small = small[cols:]
    return pack(items, cols, rows)


LAYOUT_SYSTEM = ("Ты арт-директор эстетичных эмодзи-паков Telegram. Полотно — сетка ячеек 100×100, "
                 "8 колонок. Красивые паки строятся из крупных артов (из нескольких эмодзи), баннеров "
                 "(2–4 в ширину, 1 в высоту), вертикальных разделителей (1 в ширину, 2+ в высоту) и рядов "
                 "одиночных эмодзи. Отвечаешь только JSON.")


async def ai_layout(files: list[str], description: str, ai: AIClient, cols: int = COLS, rows: int = ROWS) -> list[dict]:
    infos = [analyze(UPLOAD_DIR / f) for f in files]
    images = None
    if ai.vision:
        images = []
        for f in files[:12]:
            with Image.open(UPLOAD_DIR / f) as im:
                t = im.convert("RGB")
                t.thumbnail((256, 256))
                import io
                b = io.BytesIO()
                t.save(b, "PNG")
                images.append(b.getvalue())
    brief = [{k: i[k] for k in ("file", "w", "h", "aspect", "has_alpha", "uniform_bg", "entropy", "animated")} |
             {"hint": i["suggest"]} for i in infos]
    prompt = (f"Сетка: {cols} колонок × {rows} рядов.\nПожелания: {description or 'эстетичная общая композиция'}\n"
              f"Картинки (по порядку{', миниатюры приложены' if images else ''}):\n{json.dumps(brief, ensure_ascii=False)}\n\n"
              "Для каждой картинки реши: kind (single|big|banner|tall|collage|heart), w, h (в ячейках), "
              "remove_bg (убрать фон?), fit (cover|contain), emoji (одно подходящее эмодзи), "
              "text (короткая подпись для баннера или пусто). Порядок элементов = порядок на полотне, "
              "сделай композицию гармоничной: чередуй крупные арты, баннеры и ряды мелких.\n"
              'Формат: {"items": [{"file": "...", "kind": "...", "w": 1, "h": 1, "remove_bg": false, '
              '"fit": "cover", "emoji": "🖤", "text": ""}]}')
    data = await ai.chat_json(prompt, system=LAYOUT_SYSTEM, images=images)
    by_file = {i["file"]: i for i in infos}
    items = []
    for d in data.get("items", []):
        f = d.get("file")
        if f not in by_file:
            continue
        kind = d.get("kind") if d.get("kind") in KINDS else by_file[f]["suggest"]["kind"]
        it = {"id": f"it{len(items)}", "src": f, "kind": kind, "w": int(d.get("w") or 1), "h": int(d.get("h") or 1),
              "remove_bg": bool(d.get("remove_bg")), "fit": d.get("fit") if d.get("fit") in ("cover", "contain") else "cover",
              "emoji": (d.get("emoji") or "✨")[:8], "analysis": by_file[f]}
        if kind == "heart":
            er = rules.section("emoji")
            it.update(mask="heart", mask_mode="inside", bw=bool(er.get("hearts_bw", True)))
            if er.get("hearts_separate", True):
                it["pack"] = "hearts"
        if d.get("text"):
            it["text"] = {"content": d["text"], "size": 42, "color": "#ffffff", "stroke": 3, "stroke_color": "#000000",
                          "pos": "center", "align": "center"}
        items.append(it)
    used = {it["src"] for it in items}
    for f in files:  # то, что модель забыла — эвристикой
        if f not in used:
            s = by_file[f]["suggest"]
            items.append({"id": f"it{len(items)}", "src": f, "kind": s["kind"], "w": s["w"], "h": s["h"],
                          "remove_bg": s["remove_bg"], "fit": s["fit"], "emoji": "✨", "analysis": by_file[f]})
    return pack([rules.apply_emoji_item(it) for it in items], cols, rows)


# ---------------- рендер элемента ----------------
def _prep_frame(img: Image.Image, it: dict, box: tuple[int, int], fast: bool = False) -> Image.Image:
    if it.get("remove_bg"):
        img = trim_transparent(remove_background(img, tolerance=int(it.get("bg_tolerance", 38)),
                                                 engine=it.get("bg_engine") or None, model=it.get("bg_model") or None,
                                                 fast=fast), pad=2)
    if it.get("bw"):
        img = to_bw(img)
    mode = it.get("fit", "cover")
    focus = tuple(it.get("focus") or saliency_focus(img)) if mode == "cover" else (0.5, 0.5)
    pad = int(it.get("pad", 4 if mode == "contain" else 0))
    return fit(img, box, mode, focus=focus, pad=pad)


def _collage(srcs: list[str], box: tuple[int, int], it: dict, frame_idx: int = 0) -> Image.Image:
    W, H = box
    n = max(1, len(srcs))
    gap = int(it.get("gap", 6))
    best = None
    for c in range(1, n + 1):  # подбираем сетку под пропорции блока
        r = math.ceil(n / c)
        cell_aspect = (W / c) / (H / r)
        score = abs(math.log(cell_aspect))
        if best is None or score < best[0]:
            best = (score, c, r)
    _, c, r = best
    out = Image.new("RGBA", box, (0, 0, 0, 0))
    cw, ch = (W - gap * (c - 1)) / c, (H - gap * (r - 1)) / r
    for i, s in enumerate(srcs):
        frames, _ = load_frames(UPLOAD_DIR / s)
        fr = frames[frame_idx % len(frames)]
        cell = fit(fr, (int(cw), int(ch)), "cover", focus=saliency_focus(fr))
        cell = rounded(cell, int(it.get("radius", 10)))
        out.alpha_composite(cell, (int((i % c) * (cw + gap)), int((i // c) * (ch + gap))))
    return out


def render_item(it: dict, cell: int = CELL) -> tuple[list[Image.Image], list[int]]:
    """→ (кадры элемента размера w*cell × h*cell, длительности)."""
    box = (it["w"] * cell, it["h"] * cell)
    kind = it.get("kind", "single")
    if kind == "spacer":
        return [Image.new("RGBA", box, (0, 0, 0, 0))], [100]
    er = rules.section("emoji")
    if kind == "text" or (not it.get("src") and not it.get("srcs")):
        rule_cols = re.findall(r"#[0-9a-fA-F]{6}", er.get("banner_colors", ""))
        bg_cols = it.get("bg_colors") or rule_cols or ["#1b1b1f", "#3a2d4f"]
        base = gradient(box, bg_cols, it.get("bg_angle", 0)) if it.get("bg_style", "gradient") != "none" \
            else Image.new("RGBA", box, (0, 0, 0, 0))
        base = rounded(base, int(it.get("radius", 18)))
        frames, durs = [base], [100]
    elif kind == "collage" and it.get("srcs"):
        frames, durs = [_collage(it["srcs"], box, it)], [100]
    else:
        src_frames, durs = load_frames(UPLOAD_DIR / it["src"])
        frames = [_prep_frame(f, it, box, fast=len(src_frames) > 1) for f in src_frames]
    out = []
    for fr in frames:
        if it.get("radius") and kind not in ("text",):
            fr = rounded(fr, int(it["radius"]))
        if it.get("mask") and it["mask"] != "none":
            fr = apply_shape(fr, it["mask"], it.get("mask_mode", "inside"), int(it.get("outline", 0)),
                             it.get("outline_color", "#ffffff"))
        t = it.get("text")
        if t and t.get("content"):
            fr = draw_text_block(fr, t["content"], t.get("font") or er.get("font") or None, int(t.get("size", 40)) * cell // 100,
                                 t.get("color", "#ffffff"), int(t.get("stroke", 0)), t.get("stroke_color", "#000000"),
                                 t.get("align", "center"), t.get("pos", "center"), t.get("bg"))
        out.append(fr)
    return out, durs


# ---------------- рендер полотна и нарезка ----------------
def used_rows(items: list[dict], rows: int = ROWS) -> int:
    bottom = 0
    for it in items:
        if not it.get("overflow") and "y" in it:
            bottom = max(bottom, it["y"] + it["h"])
    return max(1, min(rows, bottom))


def render_board(items: list[dict], cols: int = COLS, rows: int = ROWS, cell: int = CELL,
                 background: str | None = None) -> dict:
    """→ {static: Image, base: Image (без анимаций), anim: [(item, frames, durs)], rows_used}."""
    rows_used = used_rows(items, rows)
    W, H = cols * cell, rows_used * cell
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    static = base.copy()
    anim = []
    for it in items:
        if it.get("overflow") or "x" not in it:
            continue
        frames, durs = render_item(it, cell)
        pos = (it["x"] * cell, it["y"] * cell)
        if len(frames) > 1:
            anim.append((it, frames, durs))
        else:
            base.alpha_composite(frames[0], pos)
        static.alpha_composite(frames[0], pos)
    preview = static
    if background:
        preview = Image.new("RGBA", static.size, background)
        preview.alpha_composite(static)
    return {"static": static, "base": base, "anim": anim, "rows_used": rows_used, "preview": preview}


def _tile_items(items: list[dict], col: int, row: int) -> list[dict]:
    return [it for it in items if not it.get("overflow") and "x" in it
            and it["x"] <= col < it["x"] + it["w"] and it["y"] <= row < it["y"] + it["h"]]


def export_board(items: list[dict], out_dir: Path, name: str, cols: int = COLS, rows: int = ROWS,
                 default_emoji: str = "✨", make_svg: bool = False, make_tgs: bool = False,
                 skip_empty_rows: bool = False, progress=None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles_dir = out_dir / "tiles"
    tiles_dir.mkdir(exist_ok=True)
    board = render_board(items, cols, rows)
    board["static"].save(out_dir / f"{name}_canvas.png")
    board["preview"].convert("RGBA").save(out_dir / f"{name}_preview.png")
    rows_used = board["rows_used"]
    manifest = []
    total = rows_used * cols
    n = 0
    for r in range(rows_used):
        row_items = [it for c in range(cols) for it in _tile_items(items, c, r)]
        if skip_empty_rows and not row_items:
            continue
        for c in range(cols):
            n += 1
            box = (c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL)
            here = _tile_items(items, c, r)
            emoji = (here[-1].get("emoji") if here else None) or default_emoji
            stem = f"{len(manifest):03d}_r{r:02d}c{c}"
            entry = {"index": len(manifest), "row": r, "col": c, "emoji": emoji, "empty": not here}
            anim_here = [(it, fr, du) for (it, fr, du) in board["anim"]
                         if it["x"] <= c < it["x"] + it["w"] and it["y"] <= r < it["y"] + it["h"]]
            if anim_here:
                it, frames, durs = anim_here[0]
                idx, fps = convert.normalize_timing(len(frames), durs)
                ox, oy = (c - it["x"]) * CELL, (r - it["y"]) * CELL
                base_tile = board["base"].crop(box)
                tile_frames = []
                for i in idx:
                    t = base_tile.copy()
                    t.alpha_composite(frames[i].crop((ox, oy, ox + CELL, oy + CELL)))
                    tile_frames.append(t)
                path = tiles_dir / f"{stem}.webm"
                convert.frames_to_webm(tile_frames, fps, path)
                convert.frames_to_gif(tile_frames, int(1000 / fps), tiles_dir / f"{stem}.gif")
                entry.update(file=str(path), format="video", gif=str(tiles_dir / f"{stem}.gif"))
                if make_tgs:
                    convert.frames_to_tgs(tile_frames, fps, tiles_dir / f"{stem}.tgs")
                    entry["tgs"] = str(tiles_dir / f"{stem}.tgs")
            else:
                tile = board["static"].crop(box)
                files = convert.save_static(tile, tiles_dir, stem)
                entry.update(file=files["webp"], png=files["png"], format="static")
                if make_svg:
                    entry["svg"] = str(tiles_dir / f"{stem}.svg")
                    entry["svg_mode"] = convert.trace_svg(Path(files["png"]), Path(entry["svg"]))
                if make_tgs:
                    convert.frames_to_tgs([tile], 1, tiles_dir / f"{stem}.tgs")
                    entry["tgs"] = str(tiles_dir / f"{stem}.tgs")
            manifest.append(entry)
            if progress:
                progress(n, total)
    (out_dir / "manifest.json").write_text(json.dumps({"name": name, "cols": cols, "tiles": manifest},
                                                       ensure_ascii=False, indent=1), "utf-8")
    zpath = out_dir.parent / f"{out_dir.name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(out_dir))
    return {"tiles": manifest, "rows_used": rows_used, "canvas": str(out_dir / f"{name}_canvas.png"),
            "zip": str(zpath), "count": len(manifest)}


# ---------------- генераторы баннеров ----------------
def make_text_banner(text: str, w_cells: int, h_cells: int, colors: list[str], font: str | None = None,
                     text_color: str = "#ffffff", deco: str = "", size: int = 46) -> Image.Image:
    box = (w_cells * CELL, h_cells * CELL)
    img = rounded(gradient(box, colors, 0), 18)
    content = f"{deco} {text} {deco}".strip() if deco else text
    return draw_text_block(img, content, font, size, text_color, stroke=0, pos="center")


def heart_strip(src: Image.Image, w_cells: int, bw: bool = True, mode: str = "inside",
                outline: int = 3) -> Image.Image:
    """Широкое сердечко на w_cells ячеек (одно сердце) — для отдельной ч/б плашки."""
    box = (w_cells * CELL, CELL)
    img = fit(src.convert("RGBA"), box, "cover", focus=saliency_focus(src))
    if bw:
        img = to_bw(img)
    return apply_shape(img, "heart", mode, outline, "#ffffff")


def grid_overlay(size: tuple[int, int], cell: int = CELL, color=(255, 255, 255, 60)) -> Image.Image:
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x in range(0, size[0] + 1, cell):
        d.line([(x, 0), (x, size[1])], fill=color)
    for y in range(0, size[1] + 1, cell):
        d.line([(0, y), (size[0], y)], fill=color)
    return im
