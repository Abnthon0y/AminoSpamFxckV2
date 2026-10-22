"""Конвертация для Telegram: WEBM (VP9 + альфа), TGS (Lottie-вектор), SVG, GIF, WEBP."""
from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

EMOJI_MAX_BYTES = 256 * 1024     # видео-эмодзи / видео-стикеры
TGS_MAX_BYTES = 64 * 1024
MAX_SECONDS = 3.0


def ffmpeg_path() -> str | None:
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:  # pip install imageio-ffmpeg — ffmpeg в комплекте
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def normalize_timing(n_frames: int, durations: list[int], max_seconds: float = MAX_SECONDS,
                     max_fps: int = 30) -> tuple[list[int], int]:
    """Подбирает индексы кадров и fps так, чтобы анимация уложилась в лимит Telegram."""
    total = sum(durations) / 1000 if durations else n_frames / 15
    speed = 1.0
    if total > max_seconds:
        speed = total / max_seconds if total <= max_seconds * 2 else 1.0  # слегка ускоряем, иначе обрезаем
    avg = (sum(durations) / max(1, len(durations))) / 1000 / speed
    fps = int(min(max_fps, max(5, round(1 / max(avg, 1e-3)))))
    times = np.cumsum([0] + [d / 1000 / speed for d in durations[:-1]])
    out_len = min(max_seconds, (sum(durations) / 1000) / speed)
    idx = []
    for k in range(max(1, int(out_len * fps))):
        t = k / fps
        idx.append(int(np.searchsorted(times, t, side="right") - 1))
    return [max(0, min(n_frames - 1, i)) for i in idx], fps


def frames_to_webm(frames: list[Image.Image], fps: int, out_path: Path, size: tuple[int, int] = (100, 100),
                   max_bytes: int = EMOJI_MAX_BYTES) -> Path:
    ff = ffmpeg_path()
    if not ff:
        raise RuntimeError("Нужен ffmpeg для анимированных эмодзи (pip install imageio-ffmpeg или установи ffmpeg)")
    tmp = Path(tempfile.mkdtemp(prefix="tgs_webm_"))
    try:
        for i, fr in enumerate(frames):
            f = fr.convert("RGBA")
            if f.size != size:
                f = f.resize(size, Image.LANCZOS)
            f.save(tmp / f"f{i:04d}.png")
        for crf in (30, 36, 42, 48, 54, 60):
            cmd = [ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%04d.png"),
                   "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", str(crf),
                   "-deadline", "good", "-an", "-t", str(MAX_SECONDS), str(out_path)]
            subprocess.run(cmd, check=True)
            if out_path.stat().st_size <= max_bytes:
                break
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def frames_to_gif(frames: list[Image.Image], durations_ms: list[int] | int, out_path: Path,
                  scale: int = 1, bg_transparent: bool = True) -> Path:
    fr = [f.resize((f.width * scale, f.height * scale), Image.NEAREST) if scale != 1 else f for f in frames]
    if isinstance(durations_ms, int):
        durations_ms = [durations_ms] * len(fr)
    pal = []
    for f in fr:
        rgba = f.convert("RGBA")
        alpha = rgba.getchannel("A")
        p = rgba.convert("RGB").quantize(255, method=Image.Quantize.MEDIANCUT)
        if bg_transparent:
            mask = alpha.point(lambda v: 255 if v < 100 else 0)
            p.paste(255, mask=mask)
            p.info["transparency"] = 255
        pal.append(p)
    pal[0].save(out_path, save_all=True, append_images=pal[1:], duration=durations_ms, loop=0,
                disposal=2, transparency=255 if bg_transparent else None, optimize=False)
    return out_path


def save_static(img: Image.Image, out_dir: Path, stem: str, size: tuple[int, int] | None = None) -> dict:
    if size and img.size != size:
        img = img.resize(size, Image.LANCZOS)
    png = out_dir / f"{stem}.png"
    webp = out_dir / f"{stem}.webp"
    img.save(png, optimize=True)
    img.save(webp, "WEBP", lossless=True, method=6)
    if webp.stat().st_size > EMOJI_MAX_BYTES:
        img.save(webp, "WEBP", quality=90, method=6)
    return {"png": str(png), "webp": str(webp)}


# ---------------- вектор ----------------
def _runs(arr: np.ndarray, alpha_thr: int = 128) -> dict[tuple, list[tuple[int, int, int, int]]]:
    """Горизонтальные серии одинаковых цветов → {цвет: [(x, y, w, h)]}. Для пиксель-арта это 1:1 вектор."""
    h, w = arr.shape[:2]
    out: dict[tuple, list] = {}
    for y in range(h):
        x = 0
        while x < w:
            px = arr[y, x]
            if px[3] < alpha_thr:
                x += 1
                continue
            key = tuple(int(v) for v in px[:3])
            x2 = x + 1
            while x2 < w and arr[y, x2][3] >= alpha_thr and tuple(int(v) for v in arr[y, x2][:3]) == key:
                x2 += 1
            out.setdefault(key, []).append((x, y, x2 - x, 1))
            x = x2
    # склеиваем одинаковые серии по вертикали
    for key, rects in out.items():
        rects.sort(key=lambda r: (r[0], r[2], r[1]))
        merged = []
        for r in rects:
            if merged and merged[-1][0] == r[0] and merged[-1][2] == r[2] and merged[-1][1] + merged[-1][3] == r[1]:
                m = merged[-1]
                merged[-1] = (m[0], m[1], m[2], m[3] + 1)
            else:
                merged.append(r)
        out[key] = merged
    return out


def quantize_small(img: Image.Image, colors: int = 24) -> np.ndarray:
    rgba = img.convert("RGBA")
    alpha = np.asarray(rgba.getchannel("A"))
    q = rgba.convert("RGB").quantize(colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.dstack([np.asarray(q), alpha])
    return arr


def pixel_svg(img: Image.Image, colors: int = 32, out_size: int = 100) -> str:
    arr = quantize_small(img, colors)
    h, w = arr.shape[:2]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{out_size}" height="{out_size}" '
             'shape-rendering="crispEdges">']
    for (r, g, b), rects in _runs(arr).items():
        d = "".join(f"M{x} {y}h{rw}v{rh}h-{rw}z" for x, y, rw, rh in rects)
        parts.append(f'<path fill="#{r:02x}{g:02x}{b:02x}" d="{d}"/>')
    parts.append("</svg>")
    return "".join(parts)


def trace_svg(img_path: Path, out_svg: Path) -> str:
    """Трассировка растра в SVG. vtracer (pip install vtracer) — настоящие кривые; иначе пиксельный вектор."""
    try:
        import vtracer  # type: ignore
        vtracer.convert_image_to_svg_py(str(img_path), str(out_svg), colormode="color", hierarchical="stacked",
                                        mode="spline", filter_speckle=2, color_precision=7,
                                        layer_difference=12, corner_threshold=60, length_threshold=4.0,
                                        max_iterations=10, splice_threshold=45, path_precision=3)
        return "vtracer"
    except ImportError:
        with Image.open(img_path) as im:
            out_svg.write_text(pixel_svg(im, 32, im.width), "utf-8")
        return "pixel"


def _lottie_color(rgb) -> list[float]:
    return [round(c / 255, 4) for c in rgb] + [1]


def _rect_shapes(arr: np.ndarray, scale: float, offset: float) -> list[dict]:
    groups = []
    for rgb, rects in _runs(arr).items():
        items = []
        for x, y, w, h in rects:
            items.append({"ty": "rc", "d": 1, "s": {"a": 0, "k": [w * scale + 0.6, h * scale + 0.6]},
                          "p": {"a": 0, "k": [offset + (x + w / 2) * scale, offset + (y + h / 2) * scale]},
                          "r": {"a": 0, "k": 0}})
        items.append({"ty": "fl", "c": {"a": 0, "k": _lottie_color(rgb)}, "o": {"a": 0, "k": 100}, "r": 1})
        items.append({"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
                      "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}})
        groups.append({"ty": "gr", "it": items, "nm": "c"})
    return groups


def frames_to_tgs(frames: list[Image.Image], fps: int, out_path: Path, colors: int = 24,
                  canvas: int = 512) -> Path:
    """Пиксельные кадры → TGS (Lottie, 60 fps, ≤3 c). Каждый кадр — слой из прямоугольников."""
    arrs = [quantize_small(f, colors) for f in frames]
    h, w = arrs[0].shape[:2]
    scale = canvas / max(w, h)
    offset = 0.0
    lottie_fps = 60
    per = max(1, round(lottie_fps / max(1, fps)))
    op = min(int(MAX_SECONDS * lottie_fps), per * len(arrs))
    layers = []
    ks = {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": [0, 0, 0]},
          "a": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]}}
    for i, arr in enumerate(arrs):
        ip = i * per
        if ip >= op:
            break
        layers.append({"ddd": 0, "ind": i + 1, "ty": 4, "nm": f"f{i}", "sr": 1, "ks": ks, "ao": 0,
                       "shapes": _rect_shapes(arr, scale, offset), "ip": ip, "op": min(op, ip + per),
                       "st": 0, "bm": 0})
    if len(arrs) == 1:
        layers[0]["op"] = op = lottie_fps  # статичный: 1 секунда
    doc = {"tgs": 1, "v": "5.7.4", "fr": lottie_fps, "ip": 0, "op": op, "w": canvas, "h": canvas,
           "nm": "tg-studio", "ddd": 0, "assets": [], "layers": layers}
    raw = json.dumps(doc, separators=(",", ":")).encode()
    out_path.write_bytes(gzip.compress(raw, 9))
    if out_path.stat().st_size > TGS_MAX_BYTES and colors > 8:
        return frames_to_tgs(frames, fps, out_path, colors=max(8, colors // 2), canvas=canvas)
    return out_path
