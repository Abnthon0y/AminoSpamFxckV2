"""Общие операции с картинками: загрузка (в т.ч. GIF), удаление фона, вписывание,
маски-формы, ч/б, обводка, шрифты."""
from __future__ import annotations

import math
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageSequence

from .config import FONTS_DIR

# ---------------- загрузка ----------------
MAX_FRAMES = 90


def load_frames(path: str | Path, max_frames: int = MAX_FRAMES) -> tuple[list[Image.Image], list[int]]:
    """→ (кадры RGBA, длительности мс). Для статичных картинок — один кадр."""
    im = Image.open(path)
    frames, durs = [], []
    if getattr(im, "is_animated", False):
        for fr in ImageSequence.Iterator(im):
            frames.append(fr.convert("RGBA"))
            durs.append(max(20, int(fr.info.get("duration", im.info.get("duration", 80)) or 80)))
        if len(frames) > max_frames:  # прореживаем, сохраняя общую длительность
            step = len(frames) / max_frames
            idx = [int(i * step) for i in range(max_frames)]
            total = sum(durs)
            frames = [frames[i] for i in idx]
            durs = [total // max_frames] * max_frames
    else:
        im = ImageOps.exif_transpose(im)
        frames, durs = [im.convert("RGBA")], [100]
    return frames, durs


def is_animated(path: str | Path) -> bool:
    try:
        with Image.open(path) as im:
            return bool(getattr(im, "is_animated", False)) and getattr(im, "n_frames", 1) > 1
    except Exception:  # noqa: BLE001
        return False


# ---------------- анализ / фон ----------------
def border_stats(img: Image.Image) -> tuple[tuple[int, int, int], float, float]:
    """→ (медианный цвет края, разброс цвета края 0..1, доля прозрачности)."""
    a = np.asarray(img.convert("RGBA").resize((96, 96)), dtype=np.float32)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    rgb = border[:, :3]
    med = np.median(rgb, axis=0)
    spread = float(np.mean(np.linalg.norm(rgb - med, axis=1)) / 441.0)
    transparency = float((a[..., 3] < 20).mean())
    return tuple(int(x) for x in med), spread, transparency


def remove_background(img: Image.Image, tolerance: int = 38, feather: float = 1.2, use_ai: bool = True) -> Image.Image:
    """Удаление фона. Если установлен rembg — нейросетевое, иначе заливка от краёв."""
    img = img.convert("RGBA")
    if use_ai:
        try:
            from rembg import remove  # type: ignore
            return remove(img)
        except Exception:  # noqa: BLE001 — rembg не установлен, работаем алгоритмом
            pass
    w, h = img.size
    rgb = img.convert("RGB")
    marker = (255, 0, 254)
    work = rgb.copy()
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    for t in range(1, 8):
        seeds += [(int(w * t / 8), 0), (int(w * t / 8), h - 1), (0, int(h * t / 8)), (w - 1, int(h * t / 8))]
    for s in seeds:
        if work.getpixel(s) != marker:
            ImageDraw.floodfill(work, s, marker, thresh=tolerance)
    m = np.asarray(work)
    bg = np.all(m == np.array(marker), axis=-1)
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    mask = Image.fromarray(alpha, "L")
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    out = img.copy()
    out.putalpha(ImageChops.multiply(mask, img.getchannel("A")))
    return out


def trim_transparent(img: Image.Image, pad: int = 0) -> Image.Image:
    bbox = img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    return img.crop((max(0, l - pad), max(0, t - pad), min(img.width, r + pad), min(img.height, b + pad)))


# ---------------- вписывание ----------------
def fit(img: Image.Image, size: tuple[int, int], mode: str = "cover", focus: tuple[float, float] = (0.5, 0.5),
        pad: int = 0, resample=Image.LANCZOS) -> Image.Image:
    W, H = size
    tw, th = W - 2 * pad, H - 2 * pad
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if tw <= 0 or th <= 0:
        return out
    if mode == "stretch":
        out.paste(img.resize((tw, th), resample), (pad, pad))
        return out
    scale = (max if mode == "cover" else min)(tw / img.width, th / img.height)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    r = img.resize((nw, nh), resample)
    if mode == "cover":
        fx, fy = focus
        left = int(max(0, min(nw - tw, fx * nw - tw / 2)))
        top = int(max(0, min(nh - th, fy * nh - th / 2)))
        r = r.crop((left, top, left + tw, top + th))
        out.alpha_composite(r, (pad, pad))
    else:
        out.alpha_composite(r, (pad + (tw - nw) // 2, pad + (th - nh) // 2))
    return out


def saliency_focus(img: Image.Image) -> tuple[float, float]:
    """Грубый центр «интересного» по градиентам — для умного кадрирования."""
    g = np.asarray(img.convert("L").resize((64, 64)), dtype=np.float32)
    gx = np.abs(np.diff(g, axis=1))[:-1]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    e = gx + gy
    if img.mode == "RGBA":
        a = np.asarray(img.getchannel("A").resize((64, 64)), dtype=np.float32)[:-1, :-1] / 255
        e = e * (0.2 + a)
    tot = e.sum()
    if tot <= 0:
        return 0.5, 0.5
    ys, xs = np.mgrid[0:e.shape[0], 0:e.shape[1]]
    return float((xs * e).sum() / tot / e.shape[1]), float((ys * e).sum() / tot / e.shape[0])


# ---------------- формы ----------------
def shape_mask(shape: str, size: tuple[int, int], ss: int = 4) -> Image.Image:
    """Маска формы (L), сглаженная суперсэмплингом. shape: heart|circle|star|rounded|arch|flower|cloud|diamond."""
    W, H = size
    w, h = W * ss, H * ss
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if shape == "heart":
        pts = []
        for i in range(721):
            t = math.pi * 2 * i / 720
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((x, -y))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        pad = 0.04
        pts = [((x - minx) / (maxx - minx) * (1 - 2 * pad) * w + pad * w,
                (y - miny) / (maxy - miny) * (1 - 2 * pad) * h + pad * h) for x, y in pts]
        d.polygon(pts, fill=255)
    elif shape == "circle":
        d.ellipse([w * 0.03, h * 0.03, w * 0.97, h * 0.97], fill=255)
    elif shape == "star":
        cx, cy, R, r = w / 2, h / 2 + h * 0.03, min(w, h) * 0.48, min(w, h) * 0.2
        pts = [(cx + (R if i % 2 == 0 else r) * math.sin(math.pi * i / 5),
                cy - (R if i % 2 == 0 else r) * math.cos(math.pi * i / 5)) for i in range(10)]
        d.polygon(pts, fill=255)
    elif shape == "arch":
        d.rounded_rectangle([0, 0, w, h], radius=0, fill=0)
        d.rectangle([w * 0.05, h * 0.45, w * 0.95, h * 0.98], fill=255)
        d.ellipse([w * 0.05, h * 0.02, w * 0.95, h * 0.02 + w * 0.9], fill=255)
    elif shape == "flower":
        cx, cy, pr = w / 2, h / 2, min(w, h) * 0.22
        for i in range(6):
            a = math.pi * 2 * i / 6
            px, py = cx + math.cos(a) * pr * 1.15, cy + math.sin(a) * pr * 1.15
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=255)
        d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=255)
    elif shape == "cloud":
        for (fx, fy, fr) in ((0.3, 0.6, 0.22), (0.5, 0.45, 0.28), (0.72, 0.6, 0.22), (0.5, 0.68, 0.22)):
            d.ellipse([w * (fx - fr), h * (fy - fr), w * (fx + fr), h * (fy + fr)], fill=255)
    elif shape == "diamond":
        d.polygon([(w / 2, h * 0.03), (w * 0.97, h / 2), (w / 2, h * 0.97), (w * 0.03, h / 2)], fill=255)
    else:  # rounded
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=min(w, h) * 0.18, fill=255)
    return m.resize((W, H), Image.LANCZOS)


def apply_shape(img: Image.Image, shape: str, mode: str = "inside", outline: int = 0,
                outline_color: str = "#ffffff") -> Image.Image:
    """inside — картинка внутри формы; erase — форма «стирает» центр (рамочка)."""
    img = img.convert("RGBA")
    m = shape_mask(shape, img.size)
    if mode == "erase":
        m = ImageOps.invert(m)
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), m))
    if outline:
        edge = shape_mask(shape, img.size)
        ring = ImageChops.subtract(edge.filter(ImageFilter.MaxFilter(outline * 2 + 1)),
                                   edge.filter(ImageFilter.MinFilter(outline * 2 + 1)))
        col = Image.new("RGBA", img.size, outline_color)
        col.putalpha(ring)
        out.alpha_composite(col)
    return out


def rounded(img: Image.Image, radius: int) -> Image.Image:
    if radius <= 0:
        return img
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=radius, fill=255)
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), m))
    return out


def to_bw(img: Image.Image, contrast: float = 1.15) -> Image.Image:
    a = img.getchannel("A")
    g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    if contrast != 1:
        g = g.point(lambda v: max(0, min(255, int((v - 128) * contrast + 128))))
    out = Image.merge("RGBA", (g, g, g, a))
    return out


def outline_alpha(img: Image.Image, width: int, color: str = "#ffffff", shadow: bool = False) -> Image.Image:
    """Обводка по контуру прозрачности (стикерный стиль) + мягкая тень."""
    if width <= 0 and not shadow:
        return img
    a = img.getchannel("A")
    W, H = img.size
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shadow:
        sh = a.filter(ImageFilter.MaxFilter(max(3, width * 2 + 1) | 1)).filter(ImageFilter.GaussianBlur(6))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.putalpha(sh.point(lambda v: int(v * 0.45)))
        out.alpha_composite(layer, (3, 5))
    if width > 0:
        k = width * 2 + 1
        grown = a
        while k > 1:  # MaxFilter умеет только нечётные размеры до разумных величин
            step = min(k, 15) | 1
            grown = grown.filter(ImageFilter.MaxFilter(step))
            k -= step - 1
        grown = grown.filter(ImageFilter.GaussianBlur(0.8)).point(lambda v: 255 if v > 90 else int(v * 2.8))
        col = Image.new("RGBA", (W, H), color)
        col.putalpha(grown)
        out.alpha_composite(col)
    out.alpha_composite(img)
    return out


# ---------------- шрифты ----------------
def _font_dirs() -> list[Path]:
    dirs = [FONTS_DIR]
    if sys.platform.startswith("win"):
        dirs += [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
                 Path.home() / "AppData/Local/Microsoft/Windows/Fonts"]
    elif sys.platform == "darwin":
        dirs += [Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path.home() / "Library/Fonts"]
    else:
        dirs += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts",
                 Path.home() / ".local/share/fonts"]
    return [d for d in dirs if d.exists()]


@lru_cache(maxsize=1)
def list_fonts() -> list[dict]:
    seen, out = set(), []
    for d in _font_dirs():
        for p in d.rglob("*"):
            if p.suffix.lower() in (".ttf", ".otf") and p.stem not in seen:
                seen.add(p.stem)
                out.append({"name": p.stem, "path": str(p)})
    out.sort(key=lambda f: f["name"].lower())
    return out


PREFERRED = ["Montserrat-Bold", "Montserrat-SemiBold", "segoeuib", "SegoeUI-Bold", "arialbd", "Arial Bold",
             "DejaVuSans-Bold", "NotoSans-Bold", "LiberationSans-Bold", "Roboto-Bold", "Helvetica"]


@lru_cache(maxsize=64)
def get_font(name: str | None, size: int) -> ImageFont.ImageFont:
    fonts = list_fonts()
    cand = None
    if name:
        cand = next((f["path"] for f in fonts if f["name"] == name or f["path"] == name), None)
    if not cand:
        for pref in PREFERRED:
            cand = next((f["path"] for f in fonts if f["name"].lower() == pref.lower()), None)
            if cand:
                break
    if not cand and fonts:
        cand = fonts[0]["path"]
    if cand:
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


FALLBACK_FONTS = ["seguisym", "Segoe UI Symbol", "seguihis", "Segoe UI Historic", "seguiemj", "Apple Symbols", "NotoSansSymbols2-Regular", "NotoSansSymbols-Regular",
                  "NotoSans-Regular", "DejaVuSans", "Symbola", "ArialUnicodeMS", "Arial Unicode", "msgothic",
                  "NotoSansCJK-Regular", "NotoSansEgyptianHieroglyphs-Regular", "unifont"]


@lru_cache(maxsize=256)
def _notdef(font_path: str, size: int) -> bytes:
    f = ImageFont.truetype(font_path, size)
    return bytes(f.getmask("\U0010FFFD"))


def _has_glyph(font, ch: str) -> bool:
    path = getattr(font, "path", None)
    if not path or ch.isspace():
        return True
    try:
        return bytes(font.getmask(ch)) != _notdef(path, font.size)
    except Exception:  # noqa: BLE001
        return True


@lru_cache(maxsize=32)
def _fallbacks(size: int) -> tuple:
    out = []
    names = {f["name"].lower(): f["path"] for f in list_fonts()}
    for n in FALLBACK_FONTS:
        p = names.get(n.lower())
        if p:
            try:
                out.append(ImageFont.truetype(p, size))
            except OSError:
                pass
    return tuple(out)


def _runs(text: str, font) -> list[tuple[str, object]]:
    """Делит строку на куски по шрифтам: основной → запасные (символы, иероглифы).
    Знаки, которых нет ни в одном шрифте, и «висячие» надстрочные знаки (࣪ ִֶָ после пробела)
    не рисуем — иначе вместо них будут квадратики и пунктирные кружки."""
    import unicodedata
    runs: list[list] = []
    prev = " "
    for ch in text:
        if unicodedata.category(ch).startswith("M") and prev.isspace():
            continue
        f = font if _has_glyph(font, ch) else next((fb for fb in _fallbacks(font.size) if _has_glyph(fb, ch)), None)
        if f is None:
            continue
        prev = ch
        if runs and runs[-1][1] is f:
            runs[-1][0] += ch
        else:
            runs.append([ch, f])
    return [(t, f) for t, f in runs]


def _line_metrics(runs, stroke: int) -> tuple[float, int, int]:
    w = sum(f.getlength(t) for t, f in runs) + stroke * 2
    asc = max((f.getmetrics()[0] for _, f in runs), default=0)
    desc = max((f.getmetrics()[1] for _, f in runs), default=0)
    return w, asc + stroke, desc + stroke


def draw_text_block(img: Image.Image, text: str, font_name: str | None, size: int, color: str = "#ffffff",
                    stroke: int = 0, stroke_color: str = "#000000", align: str = "center",
                    pos: str = "center", bg: str | None = None, margin: int = 8) -> Image.Image:
    """Рисует (многострочный) текст поверх картинки: авто-размер под ширину и запасные шрифты
    для декоративных символов (˖ ࣪ ⊹ 𓂃 ♡ …), чтобы не было «квадратиков»."""
    out = img.copy()
    W, H = out.size
    lines = text.split("\n")
    s = size
    while True:
        font = get_font(font_name, s)
        laid = [_runs(ln, font) for ln in lines]
        mets = [_line_metrics(r, stroke) for r in laid]
        spacing = s // 5
        tw = max((m[0] for m in mets), default=0)
        th = sum(m[1] + m[2] for m in mets) + spacing * (len(lines) - 1)
        if (tw <= W - 2 * margin and th <= H - 2 * margin) or s <= 8:
            break
        s -= 2
    y = {"top": margin, "bottom": H - th - margin}.get(pos, (H - th) / 2)
    if bg:
        layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
        x0 = {"left": margin, "right": W - tw - margin}.get(align, (W - tw) / 2)
        ImageDraw.Draw(layer).rounded_rectangle([x0 - margin, y - margin / 2, x0 + tw + margin, y + th + margin / 2],
                                                radius=margin, fill=bg)
        out.alpha_composite(layer)
    d = ImageDraw.Draw(out)
    for runs, (lw, asc, desc) in zip(laid, mets):
        x = {"left": margin, "right": W - lw - margin}.get(align, (W - lw) / 2) + stroke
        base = y + asc
        for t, f in runs:
            d.text((x, base), t, font=f, fill=color, anchor="ls", stroke_width=stroke, stroke_fill=stroke_color)
            x += f.getlength(t)
        y += asc + desc + spacing
    return out


def gradient(size: tuple[int, int], colors: list[str], angle: float = 90) -> Image.Image:
    from .themes.colors import hex_to_rgb
    W, H = size
    cols = [np.array(hex_to_rgb(c), dtype=np.float32) for c in (colors or ["#222222", "#444444"])]
    if len(cols) == 1:
        cols.append(cols[0])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    a = math.radians(angle)
    t = (xx * math.cos(a) + yy * math.sin(a))
    t = (t - t.min()) / max(1e-6, (t.max() - t.min()))
    seg = t * (len(cols) - 1)
    i = np.clip(seg.astype(int), 0, len(cols) - 2)
    f = (seg - i)[..., None]
    c0 = np.stack(cols)[i]
    c1 = np.stack(cols)[i + 1]
    rgb = (c0 * (1 - f) + c1 * f).astype(np.uint8)
    return Image.fromarray(rgb, "RGB").convert("RGBA")
