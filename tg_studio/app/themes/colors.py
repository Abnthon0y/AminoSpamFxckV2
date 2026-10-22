"""Цветовая математика: HEX/RGB/HSL, контраст WCAG, коррекция читаемости."""
from __future__ import annotations

import colorsys


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    r, g, b = (int(round(clamp(c, 0, 255))) for c in rgb[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def to_hsl(h: str) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in hex_to_rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, s, l


def from_hsl(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, clamp(l), clamp(s))
    return rgb_to_hex((r * 255, g * 255, b * 255))


def luminance(h: str) -> float:
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_to_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(a: str, b: str, t: float) -> str:
    """t=0 → a, t=1 → b."""
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return rgb_to_hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def with_lightness(h: str, l: float) -> str:
    hh, s, _ = to_hsl(h)
    return from_hsl(hh, s, l)


def shift(h: str, dl: float = 0.0, ds: float = 0.0, dh: float = 0.0) -> str:
    hh, s, l = to_hsl(h)
    return from_hsl(hh + dh, clamp(s + ds), clamp(l + dl))


def is_dark(h: str) -> bool:
    return luminance(h) < 0.18


def ensure_contrast(fg: str, bg: str, ratio: float = 4.5) -> str:
    """Меняет светлоту fg (сохраняя оттенок), пока контраст с bg не станет >= ratio."""
    if contrast(fg, bg) >= ratio:
        return fg
    hh, s, l = to_hsl(fg)
    go_light = luminance(bg) < 0.4
    best = fg
    for i in range(1, 101):
        nl = l + (i / 100) * ((1 - l) if go_light else -l)
        cand = from_hsl(hh, s, nl)
        best = cand
        if contrast(cand, bg) >= ratio:
            return cand
    # не вышло в эту сторону — пробуем противоположную
    alt = "#ffffff" if not go_light else "#000000"
    return alt if contrast(alt, bg) > contrast(best, bg) else best


def on_color(bg: str, tint: str | None = None, ratio: float = 4.5) -> str:
    """Читаемый текст поверх bg: почти белый/почти чёрный с лёгким оттенком."""
    base = "#ffffff" if luminance(bg) < 0.45 else "#111111"
    if tint:
        base = mix(base, tint, 0.08)
    return ensure_contrast(base, bg, ratio)


def argb_int(h: str, alpha: int = 255) -> int:
    """Знаковый ARGB int для Android .attheme."""
    r, g, b = hex_to_rgb(h)
    v = (alpha << 24) | (r << 16) | (g << 8) | b
    return v - (1 << 32) if v >= (1 << 31) else v


def rgb_int(h: str) -> int:
    r, g, b = hex_to_rgb(h)
    return (r << 16) | (g << 8) | b


def adjust_color(h: str, hue: float = 0, saturation: float = 0, lightness: float = 0,
                 contrast_amt: float = 0) -> str:
    """hue: градусы; saturation/lightness: -1..1; contrast_amt: -1..1 (растяжка светлоты от 0.5)."""
    hh, s, l = to_hsl(h)
    hh += hue
    s = clamp(s * (1 + saturation)) if saturation < 0 else clamp(s + (1 - s) * saturation)
    l = clamp(l + lightness * (1 - l) if lightness > 0 else l * (1 + lightness))
    l = clamp(0.5 + (l - 0.5) * (1 + contrast_amt))
    return from_hsl(hh, s, l)
