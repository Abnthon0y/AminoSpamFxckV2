"""Авто-стикеры: 1:1 (512×512), умное кадрирование, автокоррекция цвета,
единый стиль для всего пака, LUT-фильтры (.cube и HALD-картинки), обводка/тень/рамки."""
from __future__ import annotations

import io
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from ..config import LUT_DIR
from ..imageutil import (apply_shape, fit, outline_alpha, remove_background, rounded, saliency_focus,
                         trim_transparent)

STICKER = 512


# ---------------- LUT ----------------
def parse_cube(text: str) -> np.ndarray:
    size, data = None, []
    dmin, dmax = np.zeros(3), np.ones(3)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        up = line.upper()
        if up.startswith("LUT_3D_SIZE"):
            size = int(line.split()[-1])
        elif up.startswith("DOMAIN_MIN"):
            dmin = np.array([float(v) for v in line.split()[1:4]])
        elif up.startswith("DOMAIN_MAX"):
            dmax = np.array([float(v) for v in line.split()[1:4]])
        elif up.startswith(("TITLE", "LUT_1D")):
            continue
        elif re.match(r"^[-\d.eE+]+\s+[-\d.eE+]+\s+[-\d.eE+]+", line):
            data.append([float(v) for v in line.split()[:3]])
    if not size:
        raise ValueError("Это не 3D .cube LUT")
    arr = (np.array(data, dtype=np.float32) - dmin) / (dmax - dmin)
    # в .cube быстрее всего меняется R: индекс = r + g*N + b*N*N → lut[b, g, r]
    return arr.reshape(size, size, size, 3)


def parse_hald(img: Image.Image) -> np.ndarray:
    """HALD CLUT (например 512×512 = уровень 8 → 64³). Тоже «LUT-картинка»."""
    im = img.convert("RGB")
    w = im.width
    level = round(w ** (1 / 3))
    size = level * level
    arr = np.asarray(im, dtype=np.float32).reshape(-1, 3)[: size ** 3] / 255
    return arr.reshape(size, size, size, 3)


def identity_lut(n: int = 33) -> np.ndarray:
    g = np.linspace(0, 1, n, dtype=np.float32)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    return np.stack([r, gg, b], axis=-1)


def apply_lut(img: Image.Image, lut: np.ndarray, strength: float = 1.0) -> Image.Image:
    """Трилинейная интерполяция 3D LUT (lut[b, g, r] → rgb 0..1)."""
    a = img.getchannel("A") if img.mode == "RGBA" else None
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    n = lut.shape[0]
    x = rgb * (n - 1)
    i0 = np.floor(x).astype(np.int32).clip(0, n - 2)
    f = x - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]

    def L(db, dg, dr):
        return lut[b0 + db, g0 + dg, r0 + dr]
    c00 = L(0, 0, 0) * (1 - fr) + L(0, 0, 1) * fr
    c01 = L(0, 1, 0) * (1 - fr) + L(0, 1, 1) * fr
    c10 = L(1, 0, 0) * (1 - fr) + L(1, 0, 1) * fr
    c11 = L(1, 1, 0) * (1 - fr) + L(1, 1, 1) * fr
    c0 = c00 * (1 - fg) + c01 * fg
    c1 = c10 * (1 - fg) + c11 * fg
    out = c0 * (1 - fb) + c1 * fb
    if strength < 1:
        out = rgb * (1 - strength) + out * strength
    res = Image.fromarray((out.clip(0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
    if a is not None:
        res.putalpha(a)
    return res


def _preset_lut(fn) -> np.ndarray:
    lut = identity_lut(33)
    return fn(lut).clip(0, 1).astype(np.float32)


def _curve(x, lift=0.0, gamma=1.0, gain=1.0):
    return (lift + (np.clip(x, 0, 1) ** gamma) * (gain - lift))


def _sat(lut, k):
    l = (lut * np.array([0.299, 0.587, 0.114])).sum(-1, keepdims=True)
    return l + (lut - l) * k


PRESETS = {
    "warm_film": lambda l: _sat(np.stack([_curve(l[..., 0], 0.05, 0.92, 1.0), _curve(l[..., 1], 0.04, 0.97, 0.97),
                                          _curve(l[..., 2], 0.06, 1.05, 0.88)], -1), 0.9),
    "cool_fade": lambda l: _sat(np.stack([_curve(l[..., 0], 0.07, 1.02, 0.93), _curve(l[..., 1], 0.07, 1.0, 0.97),
                                          _curve(l[..., 2], 0.1, 0.95, 1.0)], -1), 0.85),
    "pastel": lambda l: _sat(_curve(l, 0.12, 0.85, 1.0), 0.75),
    "soft_pink": lambda l: _sat(np.stack([_curve(l[..., 0], 0.08, 0.9, 1.0), _curve(l[..., 1], 0.05, 1.0, 0.94),
                                          _curve(l[..., 2], 0.08, 0.95, 0.98)], -1), 0.85),
    "vintage": lambda l: _sat(np.stack([_curve(l[..., 0], 0.1, 0.95, 0.95), _curve(l[..., 1], 0.08, 1.0, 0.9),
                                        _curve(l[..., 2], 0.12, 1.1, 0.78)], -1), 0.7),
    "noir": lambda l: _curve(np.repeat((l * np.array([0.3, 0.59, 0.11])).sum(-1, keepdims=True), 3, -1), 0.02, 1.15, 1.0),
    "bw_soft": lambda l: _curve(np.repeat((l * np.array([0.3, 0.59, 0.11])).sum(-1, keepdims=True), 3, -1), 0.08, 0.9, 0.96),
    "vivid": lambda l: _sat(_curve(l, 0.0, 1.05, 1.0), 1.35),
    "teal_orange": lambda l: np.stack([_curve(l[..., 0], 0.0, 0.92, 1.0), _curve(l[..., 1], 0.02, 1.0, 0.97),
                                       _curve(l[..., 2], 0.08, 1.15, 0.85)], -1),
    "dreamy": lambda l: _sat(_curve(l, 0.1, 0.8, 1.0), 0.9) * np.array([1.0, 0.97, 1.03]),
}

PRESET_LABELS = {"warm_film": "Тёплая плёнка", "cool_fade": "Холодный фейд", "pastel": "Пастель",
                 "soft_pink": "Нежно-розовый", "vintage": "Винтаж", "noir": "Нуар (ч/б)", "bw_soft": "Мягкий ч/б",
                 "vivid": "Сочный", "teal_orange": "Teal & Orange", "dreamy": "Мечтательный"}


def list_luts() -> list[dict]:
    out = [{"id": f"preset:{k}", "name": PRESET_LABELS[k]} for k in PRESETS]
    for p in sorted(LUT_DIR.glob("*")):
        if p.suffix.lower() in (".cube", ".png", ".jpg", ".jpeg"):
            out.append({"id": f"file:{p.name}", "name": p.stem})
    return out


def load_lut(lut_id: str) -> np.ndarray | None:
    if not lut_id or lut_id == "none":
        return None
    kind, _, name = lut_id.partition(":")
    if kind == "preset":
        return _preset_lut(PRESETS[name])
    p = LUT_DIR / Path(name).name
    if p.suffix.lower() == ".cube":
        return parse_cube(p.read_text("utf-8", "ignore"))
    return parse_hald(Image.open(p))


def export_cube(lut: np.ndarray, title: str = "TG Studio") -> str:
    n = lut.shape[0]
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {n}"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                v = lut[b, g, r]
                lines.append(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    return "\n".join(lines) + "\n"


# ---------------- автокоррекция ----------------
def auto_correct(img: Image.Image, strength: float = 1.0) -> Image.Image:
    """Мягкая автокоррекция:
    • баланс белого по почти-нейтральным пикселям (если они есть), не больше ±12% —
      белые фоны и однотонные картинки не «уезжают» в цвет;
    • уровни: тусклые света подтягиваются, «серые» тени слегка углубляются."""
    a = img.getchannel("A") if img.mode == "RGBA" else None
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    mask = (np.asarray(a) > 20) if a is not None else np.ones(rgb.shape[:2], bool)
    px = rgb[mask] if mask.any() else rgb.reshape(-1, 3)
    mx, mn = px.max(1), px.min(1)
    neutral = px[((mx - mn) / np.maximum(mx, 1) < 0.15) & (mx > 40) & (mx < 250)]
    wb = np.ones(3, dtype=np.float32)
    if len(neutral) > 0.02 * len(px):
        m = neutral.mean(0) + 1e-3
        wb = 1 + np.clip(m.mean() / m - 1, -0.12, 0.12)
    out = rgb * wb
    lum = (px * wb) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    lo, hi = float(np.percentile(lum, 0.7)), float(np.percentile(lum, 99.5))
    new_hi = hi + min(255 - hi, hi * 0.25) if hi < 240 else hi
    new_lo = lo * 0.85 if lo > 25 else lo
    if hi - lo > 20:
        out = (out - lo) * (new_hi - new_lo) / (hi - lo) + new_lo
    out = rgb * (1 - strength) + out * strength
    res = Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGB")
    res = ImageEnhance.Color(res).enhance(1 + 0.08 * strength)
    if a is not None:
        res.putalpha(a)
    return res


def lab_stats(img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    lab = np.asarray(img.convert("RGB").convert("LAB"), dtype=np.float32).reshape(-1, 3)
    return lab.mean(0), lab.std(0) + 1e-3


def harmonize(img: Image.Image, target_mean: np.ndarray, target_std: np.ndarray, strength: float = 0.5) -> Image.Image:
    """Переносит цветовую статистику (Reinhard в LAB) — все стикеры пака в одном стиле."""
    a = img.getchannel("A") if img.mode == "RGBA" else None
    lab = np.asarray(img.convert("RGB").convert("LAB"), dtype=np.float32)
    m, s = lab.reshape(-1, 3).mean(0), lab.reshape(-1, 3).std(0) + 1e-3
    t = (lab - m) / s * target_std + target_mean
    t = lab * (1 - strength) + t * strength
    res = Image.fromarray(t.clip(0, 255).astype(np.uint8), "LAB").convert("RGB")
    if a is not None:
        res.putalpha(a)
    return res


# ---------------- оформление ----------------
FRAMES = {"none": "Без рамки", "outline": "Белая обводка (стикер)", "outline_shadow": "Обводка + тень",
          "rounded": "Скруглённые углы", "circle": "Круг", "heart": "Сердечко", "polaroid": "Полароид",
          "film": "Плёнка", "arch": "Арка"}


def stylize(img: Image.Image, frame: str, outline_w: int = 14, outline_color: str = "#ffffff",
            bg: str | None = None) -> Image.Image:
    S = STICKER
    if frame in ("outline", "outline_shadow"):
        return outline_alpha(img, outline_w, outline_color, shadow=frame == "outline_shadow")
    if frame == "rounded":
        return rounded(img, 56)
    if frame in ("circle", "heart", "arch"):
        out = apply_shape(img, frame, "inside", outline=max(0, outline_w // 2), outline_color=outline_color)
        return out
    if frame == "polaroid":
        card = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle([40, 16, S - 40, S - 16], radius=10, fill=bg or "#fbf8f2")
        photo = fit(img, (S - 120, S - 150), "cover", focus=saliency_focus(img))
        card.alpha_composite(photo, (60, 36))
        return outline_alpha(card, 0, shadow=True)
    if frame == "film":
        card = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rectangle([0, 48, S, S - 48], fill="#141414")
        for x in range(10, S, 34):
            d.rounded_rectangle([x, 58, x + 18, 72], 3, fill="#f2f2f2")
            d.rounded_rectangle([x, S - 72, x + 18, S - 58], 3, fill="#f2f2f2")
        photo = fit(img, (S - 24, S - 196), "cover", focus=saliency_focus(img))
        card.alpha_composite(photo, (12, 98))
        return card
    return img


def process(img: Image.Image, opts: dict, harmony: tuple | None = None, lut: np.ndarray | None = None) -> Image.Image:
    """opts: remove_bg, fit(cover|contain|smart), autocorrect, lut_strength, frame, outline_w, outline_color,
    padding, bg_color, brightness, contrast, saturation, warmth."""
    img = img.convert("RGBA")
    if opts.get("autocorrect", True):
        img = auto_correct(img, float(opts.get("autocorrect_strength", 0.8)))
    if harmony is not None and opts.get("harmonize", True):
        img = harmonize(img, *harmony, strength=float(opts.get("harmonize_strength", 0.35)))
    if lut is not None:
        img = apply_lut(img, lut, float(opts.get("lut_strength", 1.0)))
    for key, enh in (("brightness", ImageEnhance.Brightness), ("contrast", ImageEnhance.Contrast),
                     ("saturation", ImageEnhance.Color)):
        v = float(opts.get(key, 1.0))
        if abs(v - 1) > 1e-3:
            a = img.getchannel("A")
            img = enh(img.convert("RGB")).enhance(v).convert("RGBA")
            img.putalpha(a)
    warmth = float(opts.get("warmth", 0))
    if warmth:
        r, g, b, a = img.split()
        r = r.point(lambda v: min(255, int(v * (1 + warmth * 0.12))))
        b = b.point(lambda v: min(255, int(v * (1 - warmth * 0.12))))
        img = Image.merge("RGBA", (r, g, b, a))
    if opts.get("remove_bg"):
        img = trim_transparent(remove_background(img, tolerance=int(opts.get("bg_tolerance", 38)),
                                                 engine=opts.get("bg_engine") or None,
                                                 model=opts.get("bg_model") or None), pad=4)
    frame = opts.get("frame", "outline" if opts.get("remove_bg") else "rounded")
    room = int(outline_room(frame, int(opts.get("outline_w", 14))))
    pad = int(opts.get("padding", 0)) + room
    mode = opts.get("fit", "smart")
    if mode == "smart":
        mode = "contain" if opts.get("remove_bg") else "cover"
    canvas = fit(img, (STICKER, STICKER), mode, focus=saliency_focus(img), pad=pad)
    if opts.get("bg_color") and not opts.get("remove_bg"):
        bgc = Image.new("RGBA", canvas.size, opts["bg_color"])
        bgc.alpha_composite(canvas)
        canvas = bgc
    return stylize(canvas, frame, int(opts.get("outline_w", 14)), opts.get("outline_color", "#ffffff"))


def outline_room(frame: str, w: int) -> float:
    return w + 10 if frame.startswith("outline") else 0


def save_sticker(img: Image.Image, path: Path) -> Path:
    """WEBP 512×512 ≤ 512 КБ."""
    img = img.resize((STICKER, STICKER), Image.LANCZOS) if img.size != (STICKER, STICKER) else img
    for q in (95, 88, 80, 70, 60):
        img.save(path, "WEBP", quality=q, method=6)
        if path.stat().st_size <= 500 * 1024:
            break
    return path


def contact_sheet(paths: list[Path], cols: int = 4, cell: int = 220, bg: str = "#1c1c22") -> Image.Image:
    rows = max(1, math.ceil(len(paths) / cols))
    sheet = Image.new("RGBA", (cols * cell, rows * cell), bg)
    for i, p in enumerate(paths):
        with Image.open(p) as im:
            t = im.convert("RGBA")
            t.thumbnail((cell - 20, cell - 20))
            sheet.alpha_composite(t, ((i % cols) * cell + (cell - t.width) // 2, (i // cols) * cell + (cell - t.height) // 2))
    return sheet


def png_bytes(img: Image.Image, max_side: int = 512) -> bytes:
    im = img.copy()
    im.thumbnail((max_side, max_side))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


__all__ = ["process", "save_sticker", "load_lut", "list_luts", "apply_lut", "auto_correct", "harmonize",
           "lab_stats", "contact_sheet", "FRAMES", "PRESET_LABELS", "export_cube", "parse_cube", "parse_hald"]
