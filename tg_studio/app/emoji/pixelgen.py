"""Генератор пиксельных GIF-эмодзи по промпту.

Три режима:
  ai        — текстовая нейросеть рисует спрайт сама (JSON-сетка кадров с палитрой)
  image     — нейросеть-художник (Pollinations / Stable Diffusion) рисует картинку,
              программа превращает её в пиксель-арт и анимирует
  procedural— без интернета: встроенные спрайты + анимации
Итог: GIF-превью, WEBM 100×100 для эмодзи, TGS (вектор, чёткие пиксели), PNG-кадры.
"""
from __future__ import annotations

import colorsys
import io
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image

from .. import rules
from ..ai.providers import AIClient, generate_image
from ..imageutil import remove_background, trim_transparent
from . import convert

ANIMATIONS = {
    "none": "Без анимации", "bounce": "Прыжок", "float": "Парение", "pulse": "Пульс", "blink": "Мерцание",
    "sparkle": "Блёстки", "shine": "Блик", "rainbow": "Радуга", "shake": "Тряска", "spin": "Поворот",
    "heartbeat": "Сердцебиение", "glitch": "Глитч", "ai_frames": "Кадры рисует ИИ (режим ai)",
}

SPRITES = {
    "heart": ("""
..XX..XX..
.XHHXXXXX.
XHHXXXXXXX
XHXXXXXXXX
XXXXXXXXXX
.XXXXXXXX.
..XXXXXX..
...XXXX...
....XX....
""", {"X": "#ff4f8b", "H": "#ffd1e1"}),
    "star": ("""
....X....
....X....
...XHX...
XXXXHXXXX
.XXXXXXX.
..XXXXX..
..XX.XX..
.XX...XX.
""", {"X": "#ffd34d", "H": "#fff6c2"}),
    "sparkle": ("""
...X...
...X...
..XHX..
XXHHHXX
..XHX..
...X...
...X...
""", {"X": "#bfe9ff", "H": "#ffffff"}),
    "cherry": ("""
.....GG.
....G...
...G.G..
..G...G.
.RR..RR.
RHRR RHRR
RRRR.RRRR
.RR...RR.
""", {"G": "#3fae5a", "R": "#e23b4e", "H": "#ffb3bd"}),
    "ghost": ("""
..XXXX..
.XXXXXX.
XXBXXBXX
XXBXXBXX
XXXXXXXX
XXXXXXXX
XXXXXXXX
X.XX.XX.
""", {"X": "#f4f1ff", "B": "#2b2540"}),
    "moon": ("""
..XXX...
.XXH....
XXH.....
XXH.....
XXH.....
.XXH....
..XXXX..
""", {"X": "#ffe58a", "H": "#fff7d1"}),
    "flower": ("""
..PP.PP..
.PPPPPPP.
PPPYYYPPP
.PPYYYPP.
PPPYYYPPP
.PPPPPPP.
..PP.PP..
....G....
...GG....
""", {"P": "#ff9ccf", "Y": "#ffd84a", "G": "#4caf62"}),
    "mushroom": ("""
...RRRR...
.RRWRRRWR.
RRRRRRRRRR
RWRRRRRWRR
..SSSSSS..
..SBSSBS..
..SSSSSS..
...SSSS...
""", {"R": "#e8434f", "W": "#ffffff", "S": "#f6e3c4", "B": "#3b2a2a"}),
    "cat": ("""
X......X
XX....XX
XXXXXXXX
XEXXXXEX
XXXPPXXX
XXXXXXXX
.XXXXXX.
""", {"X": "#3a3346", "E": "#ffe066", "P": "#ff8fb1"}),
    "bow": ("""
XX....XX
XHX..XHX
XHHXXHHX
XHHXXHHX
XHX..XHX
XX....XX
""", {"X": "#ff6fa5", "H": "#ffc2d9"}),
}


def sprite_from_ascii(art: str, colors: dict) -> np.ndarray:
    lines = [ln.replace(" ", ".") for ln in art.strip("\n").splitlines()]
    w = max(len(ln) for ln in lines)
    arr = np.zeros((len(lines), w, 4), dtype=np.uint8)
    for y, ln in enumerate(lines):
        for x, ch in enumerate(ln):
            if ch in colors:
                c = colors[ch].lstrip("#")
                arr[y, x] = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    return arr


def _pad_to(arr: np.ndarray, size: int) -> np.ndarray:
    h, w = arr.shape[:2]
    if max(h, w) > size:
        im = Image.fromarray(arr, "RGBA")
        im.thumbnail((size, size), Image.NEAREST)
        arr = np.asarray(im)
        h, w = arr.shape[:2]
    out = np.zeros((size, size, 4), dtype=np.uint8)
    oy, ox = (size - h) // 2, (size - w) // 2
    out[oy:oy + h, ox:ox + w] = arr
    return out


def image_to_pixel(img: Image.Image, size: int = 24, colors: int = 12, remove_bg: bool = True) -> np.ndarray:
    img = img.convert("RGBA")
    if remove_bg:
        img = trim_transparent(remove_background(img, tolerance=45, feather=0), pad=2)
    img.thumbnail((size - 2, size - 2), Image.BOX)
    alpha = np.asarray(img.getchannel("A"))
    q = img.convert("RGB").quantize(colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.dstack([np.asarray(q), np.where(alpha > 110, 255, 0).astype(np.uint8)])
    return _pad_to(arr, size)


def add_outline(arr: np.ndarray, color=None) -> np.ndarray:
    color = color or _outline_color()
    a = arr[..., 3] > 0
    grown = a.copy()
    grown[1:] |= a[:-1]
    grown[:-1] |= a[1:]
    grown[:, 1:] |= a[:, :-1]
    grown[:, :-1] |= a[:, 1:]
    out = arr.copy()
    edge = grown & ~a
    out[edge] = color
    return out


# ---------------- анимации ----------------
def _shift(arr, dx, dy):
    out = np.zeros_like(arr)
    h, w = arr.shape[:2]
    ys, yd = (slice(max(0, -dy), h - max(0, dy)), slice(max(0, dy), h - max(0, -dy)))
    xs, xd = (slice(max(0, -dx), w - max(0, dx)), slice(max(0, dx), w - max(0, -dx)))
    out[yd, xd] = arr[ys, xs]
    return out


def _scale(arr, s):
    h, w = arr.shape[:2]
    im = Image.fromarray(arr, "RGBA")
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    r = np.asarray(im.resize((nw, nh), Image.NEAREST))
    out = np.zeros_like(arr)
    oy, ox = (h - nh) // 2, (w - nw) // 2
    sy0, sx0 = max(0, -oy), max(0, -ox)
    dy0, dx0 = max(0, oy), max(0, ox)
    ch, cw = min(nh - sy0, h - dy0), min(nw - sx0, w - dx0)
    out[dy0:dy0 + ch, dx0:dx0 + cw] = r[sy0:sy0 + ch, sx0:sx0 + cw]
    return out


def _hue(arr, deg):
    out = arr.copy()
    rgb = arr[..., :3].reshape(-1, 3) / 255
    res = np.array([colorsys.hsv_to_rgb((colorsys.rgb_to_hsv(*p)[0] + deg / 360) % 1, *colorsys.rgb_to_hsv(*p)[1:])
                    for p in rgb])
    out[..., :3] = (res.reshape(arr.shape[:2] + (3,)) * 255).astype(np.uint8)
    return out


def _bright(arr, k):
    out = arr.copy()
    out[..., :3] = np.clip(arr[..., :3].astype(np.float32) * k, 0, 255).astype(np.uint8)
    return out


def animate(base: np.ndarray, kind: str, n: int = 12, seed: int = 0) -> list[np.ndarray]:
    rnd = random.Random(seed)
    size = base.shape[0]
    frames = []
    sparkles = [(rnd.randrange(size), rnd.randrange(size), rnd.randrange(n)) for _ in range(max(3, size // 5))]
    for i in range(n):
        t = i / n
        f = base
        if kind == "bounce":
            f = _shift(base, 0, -round(abs(math.sin(t * math.pi)) * size * 0.12))
        elif kind == "float":
            f = _shift(base, 0, round(math.sin(t * 2 * math.pi) * size * 0.06))
        elif kind == "pulse":
            f = _scale(base, 1 + 0.12 * math.sin(t * 2 * math.pi))
        elif kind == "heartbeat":
            s = 1.15 if (i % (n // 2 or 1)) in (0, 1) else 1.0
            f = _scale(base, s)
        elif kind == "blink":
            f = _bright(base, 0.65 + 0.45 * (0.5 + 0.5 * math.cos(t * 2 * math.pi)))
        elif kind == "rainbow":
            f = _hue(base, 360 * t)
        elif kind == "shake":
            f = _shift(base, (-1, 1, 0, 1, -1, 0)[i % 6], 0)
        elif kind == "spin":
            sx = abs(math.cos(t * math.pi))
            im = Image.fromarray(base, "RGBA")
            w = max(1, round(size * sx))
            r = np.asarray(im.resize((w, size), Image.NEAREST))
            f = np.zeros_like(base)
            f[:, (size - w) // 2:(size - w) // 2 + w] = r
        elif kind == "glitch":
            f = base.copy()
            if i % 3 == 0:
                y = rnd.randrange(size)
                f[y:y + 2] = np.roll(f[y:y + 2], rnd.choice([-2, 2]), axis=1)
                f = _hue(f, 40) if i % 6 == 0 else f
        if kind in ("sparkle", "shine"):
            f = base.copy()
        if kind == "sparkle":
            for (x, y, ph) in sparkles:
                if (i + ph) % n < n // 3 and f[y, x, 3] == 0:
                    f[y, x] = (255, 255, 255, 255)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if (i + ph) % n == n // 6 and 0 <= x + dx < size and 0 <= y + dy < size and f[y + dy, x + dx, 3] == 0:
                            f[y + dy, x + dx] = (255, 240, 200, 255)
        if kind == "shine":
            band = int((t * 2.2 - 0.6) * size * 2)
            yy, xx = np.mgrid[0:size, 0:size]
            m = (np.abs((xx + yy) - band) < 2) & (f[..., 3] > 0)
            f[m, :3] = np.clip(f[m, :3].astype(int) + 110, 0, 255).astype(np.uint8)
        frames.append(f)
    return frames


# ---------------- генерация ----------------
PIXEL_SYSTEM = ("Ты пиксель-художник. Рисуешь милые выразительные спрайты для эмодзи Telegram. "
                "Отвечаешь только JSON.")


async def ai_sprite(prompt: str, size: int, n_frames: int, ai: AIClient) -> tuple[list[np.ndarray], int]:
    req = (f"Нарисуй пиксель-арт: «{prompt}». Размер {size}×{size}, {n_frames} кадров анимации "
           f"(если анимация не нужна — 1 кадр). Используй палитру до 12 цветов, контур тёмным цветом, "
           "объект по центру, прозрачный фон.\n"
           'Формат: {"palette": {"a": "#rrggbb", "b": "#rrggbb", ...}, "fps": 8, '
           f'"frames": [[ {size} строк по {size} символов ]]}}. '
           "Символ «.» — прозрачный пиксель, остальные символы — ключи палитры.")
    data = await ai.chat_json(req, system=PIXEL_SYSTEM, max_tokens=12000)
    pal = {k: v for k, v in (data.get("palette") or {}).items() if isinstance(v, str) and v.startswith("#")}
    frames = []
    for fr in data.get("frames") or []:
        if isinstance(fr, str):
            fr = fr.splitlines()
        art = "\n".join(str(row)[:size].ljust(size, ".") for row in fr[:size])
        if art.strip():
            frames.append(_pad_to(sprite_from_ascii(art, pal), size))
    if not frames:
        raise ValueError("Модель не нарисовала ни одного кадра")
    fps = int(data.get("fps") or 8)
    return frames, max(2, min(30, fps))


async def generate(prompt: str, mode: str = "image", size: int = 24, animation: str = "sparkle",
                   n_frames: int = 12, fps: int = 10, colors: int = 12, outline: bool = True,
                   sprite: str = "heart", seed: int | None = None, ai: AIClient | None = None,
                   source: Image.Image | None = None) -> dict:
    seed = seed if seed is not None else random.randrange(1 << 30)
    if source is not None:
        base = image_to_pixel(source, size, colors)
        frames = animate(add_outline(base) if outline else base, animation, n_frames, seed)
    elif mode == "ai":
        ai = ai or AIClient()
        frames, ai_fps = await ai_sprite(prompt, size, n_frames if animation == "ai_frames" else 1, ai)
        if animation == "ai_frames":
            fps = ai_fps
        elif animation != "none":
            frames = animate(frames[0], animation, n_frames, seed)
    elif mode == "image":
        img_bytes = await generate_image(
            f"pixel art sprite of {prompt}, single centered object, cute, bold outline, flat colors, "
            "16-bit game asset, plain white background", 512, 512, seed)
        base = image_to_pixel(Image.open(io.BytesIO(img_bytes)), size, colors)
        frames = animate(add_outline(base) if outline else base, animation, n_frames, seed)
    else:
        art, pal = SPRITES.get(sprite, SPRITES["heart"])
        base = _pad_to(sprite_from_ascii(art, pal), size)
        frames = animate(add_outline(base) if outline else base, animation, n_frames, seed)
    if animation == "none" and len(frames) > 1 and mode != "ai":
        frames = frames[:1]
    palette = rules.pixel_palette()
    if palette:  # правило: рисовать только заданными цветами
        frames = [snap_palette(f, palette) for f in frames]
    return {"frames": frames, "fps": fps, "seed": seed}


def snap_palette(arr: np.ndarray, palette: list[tuple[int, int, int]]) -> np.ndarray:
    pal = np.array(palette, dtype=np.float32)
    rgb = arr[..., :3].astype(np.float32).reshape(-1, 1, 3)
    idx = ((rgb - pal[None]) ** 2).sum(-1).argmin(1)
    out = arr.copy()
    out[..., :3] = pal[idx].reshape(arr.shape[:2] + (3,)).astype(np.uint8)
    return out


def _outline_color() -> tuple[int, int, int, int]:
    c = rules.section("pixel").get("outline_color", "").strip().lstrip("#")
    if len(c) == 6:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    return (30, 22, 40, 255)


def upscale_frames(frames: list[np.ndarray], out: int = 100) -> list[Image.Image]:
    size = frames[0].shape[0]
    k = max(1, out // size)
    res = []
    for f in frames:
        im = Image.fromarray(f, "RGBA").resize((size * k, size * k), Image.NEAREST)
        canvas = Image.new("RGBA", (out, out), (0, 0, 0, 0))
        canvas.alpha_composite(im, ((out - im.width) // 2, (out - im.height) // 2))
        res.append(canvas)
    return res


def export(frames: list[np.ndarray], fps: int, out_dir: Path, stem: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    big = upscale_frames(frames, 100)
    preview = upscale_frames(frames, 300)
    res = {"gif": str(convert.frames_to_gif(preview, int(1000 / fps), out_dir / f"{stem}.gif")),
           "png": str(out_dir / f"{stem}.png")}
    big[0].save(res["png"])
    if len(frames) > 1:
        res["webm"] = str(convert.frames_to_webm(big, fps, out_dir / f"{stem}.webm"))
    raw = [Image.fromarray(f, "RGBA") for f in frames]
    res["tgs"] = str(convert.frames_to_tgs(raw, fps, out_dir / f"{stem}.tgs", colors=16))
    (out_dir / f"{stem}.svg").write_text(convert.pixel_svg(raw[0], 16, 100), "utf-8")
    res["svg"] = str(out_dir / f"{stem}.svg")
    return res
