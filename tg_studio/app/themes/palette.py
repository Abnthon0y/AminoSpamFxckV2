"""Извлечение палитры из обоев: k-means в пространстве CIELAB (до 15 цветов)."""
from __future__ import annotations

import numpy as np
from PIL import Image

from .colors import rgb_to_hex, to_hsl


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[:, 1] - 16
    a = 500 * (f[:, 0] - f[:, 1])
    b = 200 * (f[:, 1] - f[:, 2])
    return np.stack([L, a, b], axis=1)


def extract_palette(img: Image.Image, count: int = 15, seed: int = 0, iters: int = 20) -> list[dict]:
    """Возвращает [{hex, share, h, s, l}] отсортированные по доле на картинке."""
    count = max(2, min(15, int(count)))
    im = img.convert("RGB")
    im.thumbnail((180, 180))
    px = np.asarray(im, dtype=np.float64).reshape(-1, 3)
    lab = _srgb_to_lab(px)
    rng = np.random.default_rng(seed)
    k = min(count + 4, len(lab))  # берём с запасом, потом сливаем похожие

    # k-means++
    centers = [lab[rng.integers(len(lab))]]
    for _ in range(1, k):
        d = np.min(((lab[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), axis=1)
        probs = d / d.sum() if d.sum() > 0 else None
        centers.append(lab[rng.choice(len(lab), p=probs)])
    centers = np.array(centers)

    for _ in range(iters):
        dist = ((lab[:, None, :] - centers[None]) ** 2).sum(-1)
        labels = dist.argmin(1)
        new = np.array([lab[labels == i].mean(0) if np.any(labels == i) else centers[i] for i in range(k)])
        if np.allclose(new, centers, atol=0.3):
            break
        centers = new

    dist = ((lab[:, None, :] - centers[None]) ** 2).sum(-1)
    labels = dist.argmin(1)
    clusters = []
    for i in range(k):
        mask = labels == i
        if not mask.any():
            continue
        clusters.append({"lab": centers[i], "rgb": px[mask].mean(0), "n": int(mask.sum())})

    # сливаем почти одинаковые (ΔE < 9)
    clusters.sort(key=lambda c: -c["n"])
    merged: list[dict] = []
    for c in clusters:
        for m in merged:
            if np.linalg.norm(m["lab"] - c["lab"]) < 9:
                tot = m["n"] + c["n"]
                m["rgb"] = (m["rgb"] * m["n"] + c["rgb"] * c["n"]) / tot
                m["lab"] = (m["lab"] * m["n"] + c["lab"] * c["n"]) / tot
                m["n"] = tot
                break
        else:
            merged.append(dict(c))

    merged = merged[:count]
    total = sum(m["n"] for m in merged) or 1
    out = []
    for m in merged:
        hx = rgb_to_hex(m["rgb"])
        h, s, l = to_hsl(hx)
        out.append({"hex": hx, "share": round(m["n"] / total, 4), "h": round(h, 1), "s": round(s, 3), "l": round(l, 3)})
    return out


def wallpaper_brightness(img: Image.Image) -> float:
    im = img.convert("L")
    im.thumbnail((64, 64))
    return float(np.asarray(im).mean() / 255)
