"""Генерация семантических ролей темы из палитры (алгоритм + нейросеть)."""
from __future__ import annotations

import random
import re

from .colors import (clamp, contrast, ensure_contrast, from_hsl, luminance, mix, on_color,
                     shift, to_hsl)

ROLE_KEYS = [
    "bg", "bg2", "surface", "header", "header_text", "header_icon",
    "accent", "on_accent", "text", "text2", "icon", "divider", "link", "online", "badge_muted",
    "chat_bg", "in_bubble", "in_text", "in_secondary", "in_accent",
    "out_bubble", "out_bubble2", "out_text", "out_secondary", "out_accent",
    "service_bg", "service_text", "input_bg", "input_text", "selection",
]

ROLE_LABELS = {
    "bg": "Фон списка чатов", "bg2": "Второй фон (настройки)", "surface": "Панели и меню",
    "header": "Шапка", "header_text": "Текст шапки", "header_icon": "Иконки шапки",
    "accent": "Акцент", "on_accent": "Текст на акценте", "text": "Основной текст",
    "text2": "Второстепенный текст", "icon": "Иконки", "divider": "Разделители",
    "link": "Ссылки", "online": "Онлайн", "badge_muted": "Счётчик без звука",
    "chat_bg": "Фон чата", "in_bubble": "Входящее сообщение", "in_text": "Текст входящего",
    "in_secondary": "Время во входящем", "in_accent": "Акцент входящего",
    "out_bubble": "Исходящее сообщение", "out_bubble2": "Градиент исходящего",
    "out_text": "Текст исходящего", "out_secondary": "Время в исходящем", "out_accent": "Акцент исходящего",
    "service_bg": "Плашки дат", "service_text": "Текст плашек", "input_bg": "Поле ввода",
    "input_text": "Текст поля ввода", "selection": "Выделение",
}

# (передний план, фон, минимальный контраст)
CONTRAST_RULES = [
    ("text", "bg", 7.0), ("text2", "bg", 4.5), ("text", "surface", 7.0), ("text2", "surface", 4.5),
    ("header_text", "header", 4.5), ("header_icon", "header", 3.0),
    ("on_accent", "accent", 4.5), ("icon", "bg", 3.0), ("link", "bg", 4.5),
    ("in_text", "in_bubble", 7.0), ("in_secondary", "in_bubble", 3.5), ("in_accent", "in_bubble", 4.5),
    ("out_text", "out_bubble", 7.0), ("out_text", "out_bubble2", 4.5),
    ("out_secondary", "out_bubble", 3.5), ("out_accent", "out_bubble", 4.5),
    ("service_text", "service_bg", 4.5), ("input_text", "input_bg", 7.0),
]

# для этих пар меняем только фон (градиент подстраивается под уже выбранный текст)
BG_ONLY_RULES = {("out_text", "out_bubble2")}

STYLES = {
    "tinted": "Тонированные пузыри",
    "solid": "Сочный акцентный пузырь",
    "pastel": "Пастель",
    "glass": "Стекло / минимализм",
    "duo": "Два акцента",
    "mono": "Монохром",
}


def _accent_candidates(palette: list[dict]) -> list[str]:
    def score(p):
        h, s, l = to_hsl(p["hex"])
        return s * (1 - abs(l - 0.55) * 1.4) * (0.35 + p.get("share", 0.05)) ** 0.35
    ranked = sorted(palette, key=score, reverse=True)
    out = []
    for p in ranked:
        if all(abs(to_hsl(p["hex"])[0] - to_hsl(o)[0]) % 360 > 18 for o in out):
            out.append(p["hex"])
    return out or [palette[0]["hex"]]


def build_theme(palette: list[dict], mode: str = "auto", style: str = "tinted", variant: int = 0,
                wall_brightness: float | None = None) -> dict:
    """palette — список {hex, share}. Возвращает словарь ролей (все ключи ROLE_KEYS)."""
    if not palette:
        palette = [{"hex": "#6c5ce7", "share": 1.0}]
    rnd = random.Random(variant * 7919 + len(palette))
    if mode == "auto":
        avg_l = wall_brightness if wall_brightness is not None else sum(
            to_hsl(p["hex"])[2] * p.get("share", 1 / len(palette)) for p in palette)
        mode = "dark" if avg_l < 0.55 else "light"
    dark = mode == "dark"

    accents = _accent_candidates(palette)
    accent = accents[variant % len(accents)]
    accent2 = accents[(variant + 1) % len(accents)] if len(accents) > 1 else shift(accent, dh=40)
    dominant = max(palette, key=lambda p: p.get("share", 0))["hex"]

    ah, as_, al = to_hsl(accent)
    dh, ds, _ = to_hsl(dominant)
    base_h = dh if ds > 0.08 else ah
    if style == "mono":
        base_h = ah

    sat_bg = min(ds, 0.32) * (0.6 + rnd.random() * 0.5)
    if dark:
        bg = from_hsl(base_h, sat_bg, 0.075 + rnd.random() * 0.04)
        bg2 = shift(bg, dl=-0.025)
        surface = shift(bg, dl=0.045)
        divider = shift(bg, dl=0.09, ds=-0.05)
    else:
        bg = from_hsl(base_h, sat_bg * 0.8, 0.975 - rnd.random() * 0.02)
        bg2 = shift(bg, dl=-0.04)
        surface = "#ffffff" if sat_bg < 0.1 else shift(bg, dl=0.015)
        divider = shift(bg, dl=-0.1, ds=-0.05)

    # акцент делаем «живым»: достаточно насыщенным и читаемым на фоне
    accent = from_hsl(ah, max(as_, 0.45), clamp(al, 0.42, 0.7) if dark else clamp(al, 0.35, 0.58))
    accent = ensure_contrast(accent, bg, 3.0)
    accent2 = ensure_contrast(from_hsl(to_hsl(accent2)[0], max(to_hsl(accent2)[1], 0.4), to_hsl(accent)[2]), bg, 3.0)

    text = on_color(bg, accent, 7.0)

    header_style = rnd.choice(["bg", "accent", "surface"]) if style != "mono" else "bg"
    header = {"bg": surface if dark else bg, "accent": accent if not dark else shift(accent, dl=-0.18),
              "surface": surface}[header_style]

    # пузыри
    if style == "solid":
        out_b = accent
        in_b = surface
    elif style == "pastel":
        out_b = mix(accent, "#ffffff", 0.55) if not dark else mix(accent, bg, 0.55)
        in_b = mix(accent2, "#ffffff", 0.75) if not dark else mix(accent2, bg, 0.78)
    elif style == "glass":
        out_b = mix(surface, accent, 0.18)
        in_b = surface
    elif style == "duo":
        out_b = mix(accent, bg, 0.35)
        in_b = mix(accent2, bg, 0.6)
    elif style == "mono":
        out_b = mix(accent, bg, 0.5)
        in_b = shift(surface, dl=0.02 if dark else -0.02)
    else:  # tinted
        out_b = mix(accent, bg, 0.42 if dark else 0.72)
        in_b = surface if dark else "#ffffff"
    out_b2 = shift(out_b, dh=18 + rnd.random() * 20, dl=0.03 * (1 if dark else -1)) if style in ("solid", "duo", "pastel") else out_b

    chat_bg = shift(bg, dl=0.02 if dark else -0.06, ds=0.05)
    roles = derive_roles({"bg": bg, "bg2": bg2, "surface": surface, "divider": divider, "header": header,
                          "accent": accent, "accent2": accent2, "chat_bg": chat_bg, "in_bubble": in_b,
                          "out_bubble": out_b, "out_bubble2": out_b2, "text": text}, style)
    roles["_meta"] = {"mode": mode, "style": style, "variant": variant}
    return fix_contrast(roles)


CORE_KEYS = ["bg", "surface", "header", "accent", "accent2", "chat_bg", "in_bubble", "out_bubble", "out_bubble2"]


def derive_roles(c: dict, style: str = "") -> dict:
    """Достраивает все роли из ключевых цветов (core). Отсутствующие ключи выводятся из bg/accent."""
    bg = c["bg"]
    dark = luminance(bg) < 0.3
    accent = c.get("accent") or "#8f7bff"
    accent2 = c.get("accent2") or shift(accent, dh=40)
    surface = c.get("surface") or shift(bg, dl=0.045 if dark else 0.015)
    bg2 = c.get("bg2") or shift(bg, dl=-0.025 if dark else -0.04)
    divider = c.get("divider") or shift(bg, dl=0.09 if dark else -0.1, ds=-0.05)
    header = c.get("header") or surface
    in_b = c.get("in_bubble") or surface
    out_b = c.get("out_bubble") or mix(accent, bg, 0.42 if dark else 0.72)
    out_b2 = c.get("out_bubble2") or out_b
    text = c.get("text") or on_color(bg, accent, 7.0)
    text2 = ensure_contrast(mix(text, bg, 0.45), bg, 4.5)
    in_text = on_color(in_b, accent, 7.0)
    out_text = on_color(out_b, accent, 7.0)
    return {
        "bg": bg, "bg2": bg2, "surface": surface, "header": header,
        "header_text": on_color(header, accent, 4.5), "header_icon": on_color(header, accent, 3.0),
        "accent": accent, "on_accent": on_color(accent, None, 4.5),
        "text": text, "text2": text2, "icon": ensure_contrast(mix(text2, accent, 0.25), bg, 3.0), "divider": divider,
        "link": ensure_contrast(accent, bg, 4.5), "online": ensure_contrast(accent2, bg, 3.0),
        "badge_muted": mix(text2, bg, 0.35),
        "chat_bg": c.get("chat_bg") or shift(bg, dl=0.02 if dark else -0.06, ds=0.05),
        "in_bubble": in_b, "in_text": in_text,
        "in_secondary": ensure_contrast(mix(in_text, in_b, 0.5), in_b, 3.5),
        "in_accent": ensure_contrast(accent, in_b, 4.5),
        "out_bubble": out_b, "out_bubble2": out_b2, "out_text": out_text,
        "out_secondary": ensure_contrast(mix(out_text, out_b, 0.45), out_b, 3.5),
        "out_accent": ensure_contrast(accent2 if style == "solid" else accent, out_b, 4.5),
        "service_bg": mix(bg, "#000000", 0.35) if dark else mix(accent, "#000000", 0.45),
        "service_text": "#ffffff",
        "input_bg": surface, "input_text": on_color(surface, accent, 7.0),
        "selection": mix(accent, bg, 0.7),
    }


def fix_contrast(roles: dict, boost: float = 0.0, locked: dict | None = None) -> dict:
    """boost — усиление требований к контрасту (0.2 = на 20% строже), locked — роли, которые нельзя менять."""
    out = dict(roles)
    locked = locked or {}
    out.update(locked)
    for k in ROLE_KEYS:
        if k not in out or not isinstance(out[k], str) or not out[k].startswith("#"):
            out[k] = "#888888"
    for _ in range(2):
        for fg, bg, ratio in CONTRAST_RULES:
            ratio = min(21.0, ratio * (1 + boost))
            if (fg, bg) not in BG_ONLY_RULES and fg not in locked:
                out[fg] = ensure_contrast(out[fg], out[bg], ratio)
            if contrast(out[fg], out[bg]) < ratio - 0.01 and bg not in ("bg", "surface") and bg not in locked:
                # текст уже предельный (почти белый/чёрный) — двигаем светлоту фона
                h, s, l = to_hsl(out[bg])
                away = -1 if luminance(out[fg]) > luminance(out[bg]) else 1
                for i in range(1, 60):
                    cand = from_hsl(h, s, clamp(l + away * i * 0.01))
                    if contrast(out[fg], cand) >= ratio:
                        out[bg] = cand
                        break
    return out


def contrast_report(roles: dict, boost: float = 0.0) -> list[dict]:
    rep = []
    for fg, bg, ratio in CONTRAST_RULES:
        ratio = round(min(21.0, ratio * (1 + boost)), 2)
        c = contrast(roles[fg], roles[bg])
        rep.append({"fg": fg, "bg": bg, "ratio": round(c, 2), "need": ratio, "ok": c >= ratio - 0.01})
    return rep


def theme_variants(palette: list[dict], mode: str, count: int = 6, wall_brightness: float | None = None,
                   styles: list[str] | None = None) -> list[dict]:
    styles = [s for s in (styles or []) if s in STYLES] or list(STYLES)
    out = []
    for i in range(count):
        st = styles[i % len(styles)]
        t = build_theme(palette, mode, st, variant=i // len(styles) + i, wall_brightness=wall_brightness)
        out.append(t)
    return out


AI_SYSTEM = (
    "Ты — дизайнер тем для Telegram. Создаёшь уникальные, эстетичные и при этом контрастные темы: "
    "все тексты должны легко читаться (WCAG: основной текст ≥ 7:1, вторичный ≥ 4.5:1). "
    "Используешь цвета из палитры обоев, но можешь смещать светлоту/насыщенность. Отвечаешь только JSON."
)


def ai_prompt(palette: list[dict], description: str, mode: str, count: int) -> str:
    pal = ", ".join(f"{p['hex']} ({round(p.get('share', 0) * 100)}%)" for p in palette)
    core = ", ".join(CORE_KEYS)
    return (
        f"Палитра обоев: {pal}\n"
        f"Режим: {mode} (auto = выбери сам по обоям)\n"
        f"Пожелания: {description or 'уникально, эстетично, контрастно'}\n\n"
        f"Сделай {count} разных варианта темы — только ключевые цвета, остальное программа рассчитает сама.\n"
        "bg — фон списка чатов, surface — панели, header — шапка, accent/accent2 — акценты, chat_bg — фон чата, "
        "in_bubble/out_bubble — входящие/исходящие сообщения, out_bubble2 — второй цвет градиента исходящих.\n"
        'Формат: {"themes": [{"name": "короткое красивое название", '
        f'"colors": {{{core} — HEX #rrggbb}}}}]}}'
    )


def normalize_ai_themes(data, palette: list[dict]) -> list[dict]:
    themes = data.get("themes") if isinstance(data, dict) else data
    out = []
    for t in themes or []:
        if not isinstance(t, dict):
            continue
        cols = t.get("colors") or t.get("roles") or {}
        core = {}
        for k, v in cols.items():
            if isinstance(v, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", v.strip()):
                core[k] = "#" + v.strip().lstrip("#").lower()
        if "bg" not in core:
            core["bg"] = build_theme(palette, t.get("mode", "auto"))["bg"]
        roles = fix_contrast(derive_roles(core))
        roles["_meta"] = {"mode": "dark" if luminance(roles["bg"]) < 0.3 else "light", "style": "ai",
                          "name": t.get("name") or "AI тема"}
        out.append(roles)
    if not out:
        raise ValueError("Нейросеть не прислала ни одной темы — попробуй ещё раз")
    return out
