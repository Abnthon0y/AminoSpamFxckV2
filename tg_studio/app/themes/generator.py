"""Генерация семантических ролей темы из палитры (алгоритм + нейросеть)."""
from __future__ import annotations

import json
import random
import re

from .colors import (clamp, contrast, ensure_contrast, from_hsl, luminance, mix, on_color,
                     shift, to_hsl)

ROLE_GROUPS = [
    ("Основа", ["bg", "bg2", "surface", "divider", "selection", "accent", "accent2", "on_accent"]),
    ("Шапка", ["header", "header_text", "header_subtitle", "header_icon"]),
    ("Список чатов", ["text", "text2", "chat_date", "icon", "badge", "badge_text", "badge_muted", "online",
                      "pinned_bg", "fab_bg", "fab_icon"]),
    ("Фон чата и плашки", ["chat_bg", "service_bg", "service_text"]),
    ("Входящие сообщения", ["in_bubble", "in_text", "in_secondary", "in_accent", "in_name", "in_link"]),
    ("Исходящие сообщения", ["out_bubble", "out_bubble2", "out_text", "out_secondary", "out_accent", "out_link",
                             "out_check"]),
    ("Поле ввода", ["input_bg", "input_text", "input_hint", "input_icon", "send_btn"]),
    ("Меню и окна", ["dialog_bg", "menu_text", "menu_icon", "emoji_panel_bg"]),
    ("Кнопки и переключатели", ["button_bg", "button_text", "link", "switch_on", "switch_off", "checkbox",
                                "tab_active", "progress"]),
    ("Статусы", ["error", "success"]),
    ("Истории", ["story1", "story2", "story_close1", "story_close2"]),
    ("Статистика", ["chart_blue", "chart_green", "chart_red", "chart_golden", "chart_lightblue", "chart_lightgreen",
                    "chart_orange", "chart_indigo", "chart_purple", "chart_cyan", "chart_grid", "chart_text"]),
]
CHART_KEYS = ["chart_blue", "chart_green", "chart_red", "chart_golden", "chart_lightblue", "chart_lightgreen",
              "chart_orange", "chart_indigo", "chart_purple", "chart_cyan"]
CHART_HUES = dict(zip(CHART_KEYS, [214, 140, 356, 46, 196, 96, 24, 250, 290, 170]))
ROLE_KEYS = [k for _, keys in ROLE_GROUPS for k in keys]

ROLE_LABELS = {
    "bg": "Фон списка чатов", "bg2": "Второй фон (настройки)", "surface": "Панели (вкладки, плеер)",
    "divider": "Разделители", "selection": "Выделение", "accent": "Акцент", "accent2": "Второй акцент",
    "on_accent": "Текст на акценте",
    "header": "Шапка", "header_text": "Заголовок в шапке", "header_subtitle": "Подзаголовок (статус)",
    "header_icon": "Иконки шапки",
    "text": "Имена / основной текст", "text2": "Последнее сообщение / вторичный", "chat_date": "Время в списке",
    "icon": "Иконки", "badge": "Счётчик непрочитанных", "badge_text": "Цифра на счётчике",
    "badge_muted": "Счётчик без звука", "online": "Онлайн / галочки", "pinned_bg": "Закреплённые чаты",
    "fab_bg": "Круглая кнопка «написать»", "fab_icon": "Иконка на круглой кнопке",
    "chat_bg": "Фон чата (без обоев)", "service_bg": "Плашки дат", "service_text": "Текст плашек",
    "in_bubble": "Пузырь", "in_text": "Текст", "in_secondary": "Время", "in_accent": "Ответы / файлы",
    "in_name": "Имя отправителя", "in_link": "Ссылки",
    "out_bubble": "Пузырь", "out_bubble2": "Второй цвет градиента", "out_text": "Текст", "out_secondary": "Время",
    "out_accent": "Ответы / файлы", "out_link": "Ссылки", "out_check": "Галочки прочтения",
    "input_bg": "Фон панели ввода", "input_text": "Вводимый текст", "input_hint": "Подсказка «Сообщение»",
    "input_icon": "Иконки (скрепка, смайл)", "send_btn": "Кнопка отправки",
    "dialog_bg": "Фон меню и окон", "menu_text": "Текст меню", "menu_icon": "Иконки меню",
    "emoji_panel_bg": "Панель эмодзи и стикеров",
    "button_bg": "Кнопки", "button_text": "Текст кнопок", "link": "Ссылки в настройках",
    "switch_on": "Переключатель вкл.", "switch_off": "Переключатель выкл.", "checkbox": "Галочки-чекбоксы",
    "tab_active": "Активная вкладка", "progress": "Полосы загрузки / плеер",
    "error": "Ошибки / удаление", "success": "Успех",
    "story1": "Кольцо истории (начало градиента)", "story2": "Кольцо истории (конец градиента)",
    "story_close1": "Близкие друзья (начало)",
    "story_close2": "Близкие друзья (конец)",
    "chart_blue": "Линия 1 (синяя)", "chart_green": "Линия 2 (зелёная)", "chart_red": "Линия 3 (красная)",
    "chart_golden": "Линия 4 (золотая)", "chart_lightblue": "Линия 5 (голубая)",
    "chart_lightgreen": "Линия 6 (салатовая)", "chart_orange": "Линия 7 (оранжевая)",
    "chart_indigo": "Линия 8 (индиго)", "chart_purple": "Линия 9 (фиолетовая)", "chart_cyan": "Линия 10 (бирюзовая)",
    "chart_grid": "Сетка графика", "chart_text": "Подписи графика",
}

# (передний план, фон, минимальный контраст)
CONTRAST_RULES = [
    ("text", "bg", 7.0), ("text2", "bg", 4.5), ("chat_date", "bg", 3.5), ("text", "surface", 7.0),
    ("text2", "surface", 4.5), ("header_text", "header", 4.5), ("header_subtitle", "header", 3.0),
    ("header_icon", "header", 3.0), ("on_accent", "accent", 4.5), ("icon", "bg", 3.0), ("link", "bg", 4.5),
    ("badge_text", "badge", 4.5), ("fab_icon", "fab_bg", 3.0),
    ("in_text", "in_bubble", 7.0), ("in_secondary", "in_bubble", 3.5), ("in_accent", "in_bubble", 4.5),
    ("in_name", "in_bubble", 4.5), ("in_link", "in_bubble", 4.5),
    ("out_text", "out_bubble", 7.0), ("out_text", "out_bubble2", 4.5),
    ("out_secondary", "out_bubble", 3.5), ("out_accent", "out_bubble", 4.5), ("out_link", "out_bubble", 4.5),
    ("out_check", "out_bubble", 3.0),
    ("service_text", "service_bg", 4.5), ("input_text", "input_bg", 7.0), ("input_hint", "input_bg", 3.5),
    ("input_icon", "input_bg", 3.0), ("send_btn", "input_bg", 3.0),
    ("menu_text", "dialog_bg", 7.0), ("menu_icon", "dialog_bg", 3.0), ("button_text", "button_bg", 4.5),
    ("error", "bg", 3.0), ("success", "bg", 3.0),
    ("story1", "bg", 3.0), ("story2", "bg", 3.0), ("story_close1", "bg", 3.0), ("story_close2", "bg", 3.0),
    ("chart_text", "bg", 4.5),
] + [(k, "bg", 3.0) for k in CHART_KEYS]  # линии графиков — не ниже 3:1 к фону (WCAG для графики)

# ---------------- эффекты: прозрачность и тени ----------------
FX_DEFAULT = {
    "in_alpha": 100, "out_alpha": 100,          # прозрачность пузырей, %
    "service_alpha": 80, "input_alpha": 100,     # плашки дат, панель ввода
    "selection_alpha": 60,
    "shadow_in": "#000000", "shadow_in_alpha": 0,     # тень входящих: цвет и сила, %
    "shadow_out": "#000000", "shadow_out_alpha": 0,   # тень исходящих
    "animated_gradient": False,                  # анимированный градиент исходящих (облачная тема)
    "wall": "",                                  # средний цвет обоев — для честной проверки контраста
}
FX_LABELS = {
    "in_alpha": "Непрозрачность входящих", "out_alpha": "Непрозрачность исходящих",
    "service_alpha": "Непрозрачность плашек дат", "input_alpha": "Непрозрачность панели ввода",
    "selection_alpha": "Непрозрачность выделения", "shadow_in_alpha": "Тень входящих",
    "shadow_out_alpha": "Тень исходящих",
}
# какая роль-фон становится полупрозрачной от какого параметра
ALPHA_BG = {"in_bubble": "in_alpha", "out_bubble": "out_alpha", "out_bubble2": "out_alpha",
            "service_bg": "service_alpha", "input_bg": "input_alpha"}


def sanitize_fx(fx: dict | None) -> dict:
    out = dict(FX_DEFAULT)
    for k, v in (fx or {}).items():
        if k not in FX_DEFAULT:
            continue
        d = FX_DEFAULT[k]
        if isinstance(d, bool):
            out[k] = bool(v)
        elif isinstance(d, int):
            try:
                out[k] = int(max(0, min(100, float(v))))
            except (TypeError, ValueError):
                pass
        elif isinstance(v, str) and (not v or re.fullmatch(r"#?[0-9a-fA-F]{6}", v.strip())):
            out[k] = ("#" + v.strip().lstrip("#").lower()) if v else ""
    out["in_alpha"] = max(out["in_alpha"], 15)   # совсем невидимый пузырь не читается
    out["out_alpha"] = max(out["out_alpha"], 15)
    return out


def effective(roles: dict, bg_role: str) -> str:
    """Цвет фона с учётом прозрачности: полупрозрачный пузырь смешивается с обоями/фоном чата."""
    fx = sanitize_fx(roles.get("_fx"))
    key = ALPHA_BG.get(bg_role)
    if not key or fx[key] >= 100:
        return roles[bg_role]
    under = fx["wall"] or roles.get("chat_bg") or roles["bg"]
    return mix(under, roles[bg_role], fx[key] / 100)


def spread_charts(out: dict, locked: dict | None = None) -> None:
    """Линии статистики должны различаться: близкие по оттенку и светлоте — разводим по кругу."""
    seen: list[tuple[float, float]] = []
    for k in CHART_KEYS:
        h, s_, l = to_hsl(out[k])
        for _ in range(12):
            close = any(min(abs(h - h2), 360 - abs(h - h2)) < 12 and abs(l - l2) < 0.12 for h2, l2 in seen)
            if not close or (locked and k in locked):
                break
            h = (h + 29) % 360
        out[k] = from_hsl(h, max(s_, 0.35), l)
        seen.append((h, l))

def theme_charts(roles: dict, locked: dict | None = None, pull: float = 0.22) -> dict:
    """Все 10 линий статистики в духе темы: каждая сохраняет свой оттенок (синяя остаётся синеватой),
    но притянута к акценту на pull, насыщенность как у акцента, светлота — под контраст ≥ 3:1 к фону.
    Потом линии разводятся, чтобы не сливались."""
    h0, s0, _ = to_hsl(roles.get("accent", "#8f7bff"))
    bg = roles.get("bg", "#ffffff")
    l = 0.64 if luminance(bg) < 0.3 else 0.44
    out = {}
    for k in CHART_KEYS:
        if locked and k in locked:
            out[k] = locked[k]
            continue
        h = CHART_HUES[k]
        d = (h0 - h + 540) % 360 - 180  # кратчайший путь по кругу к акценту
        out[k] = ensure_contrast(from_hsl((h + d * pull) % 360, clamp(s0 * 0.9, 0.45, 0.8), l), bg, 3.0)
    spread_charts(out, locked)
    for k in CHART_KEYS:
        out[k] = ensure_contrast(out[k], bg, 3.0)
    return {k: v for k, v in out.items() if not (locked and k in locked)}


EDIT_HINTS = [  # частые просьбы, которые слабые модели выполняют наполовину — доделываем сами
    (re.compile(r"статистик|график|chart", re.I), "charts"),
    (re.compile(r"стекл|прозрачн|glass", re.I), "glass"),
    (re.compile(r"тен[ьи]|shadow", re.I), "shadow"),
    (re.compile(r"истори|stor", re.I), "stories"),
]


def complete_edit(roles: dict, data: dict, instruction: str, locked: dict | None = None) -> dict:
    """Дополняет ответ ИИ, если он сделал просьбу частично (одна линия статистики из десяти,
    прозрачность только у исходящих и т. п.)."""
    data = dict(data or {})
    r = dict(data.get("roles") or {})
    fx = dict(data.get("fx") or {})
    hints = {tag for rx, tag in EDIT_HINTS if rx.search(instruction or "")}
    if "charts" in hints and sum(k in r for k in CHART_KEYS) < len(CHART_KEYS) // 2:
        r.update(theme_charts({**roles, **_hex_roles(r)}, locked))
    if "glass" in hints and not re.search(r"убер|без|не\s+нужн|сплошн", instruction, re.I):
        cur = sanitize_fx({**(roles.get("_fx") or {}), **fx})
        if cur["in_alpha"] >= 95 and cur["out_alpha"] >= 95:
            fx.update(in_alpha=65, out_alpha=72)
        elif cur["in_alpha"] >= 95:
            fx["in_alpha"] = max(55, cur["out_alpha"] - 7)
        elif cur["out_alpha"] >= 95:
            fx["out_alpha"] = min(85, cur["in_alpha"] + 7)
        fx.setdefault("service_alpha", min(cur["service_alpha"], 60))
    if "shadow" in hints and not re.search(r"убер|без|не\s+нужн", instruction, re.I):
        cur = sanitize_fx({**(roles.get("_fx") or {}), **fx})
        if not cur["shadow_in_alpha"] and not cur["shadow_out_alpha"]:
            fx.update(shadow_in_alpha=25, shadow_out_alpha=25)
        elif not cur["shadow_in_alpha"]:
            fx.update(shadow_in=cur["shadow_out"], shadow_in_alpha=cur["shadow_out_alpha"])
        elif not cur["shadow_out_alpha"]:
            fx.update(shadow_out=cur["shadow_in"], shadow_out_alpha=cur["shadow_in_alpha"])
    if "stories" in hints and not any(k in r for k in ("story1", "story2")):
        r.update(story1=roles.get("accent"), story2=roles.get("accent2") or roles.get("accent"))
    data["roles"], data["fx"] = r, fx
    return data


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
    out = {
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
    out.update({k: v for k, v in c.items() if k in ROLE_KEYS and isinstance(v, str) and v.startswith("#")})
    o = out  # производные детальные роли (по умолчанию — от базовых)
    defaults = {
        "accent2": accent2,
        "header_subtitle": ensure_contrast(mix(o["header_text"], o["header"], 0.3), o["header"], 3.0),
        "chat_date": o["text2"],
        "badge": o["accent"], "pinned_bg": mix(o["bg"], o["accent"], 0.06),
        "fab_bg": o["accent"],
        "in_name": o["in_accent"], "in_link": o["in_accent"],
        "out_link": o["out_accent"], "out_check": o["out_accent"],
        "input_hint": ensure_contrast(mix(o["input_text"], o["input_bg"], 0.5), o["input_bg"], 3.5),
        "input_icon": ensure_contrast(mix(o["icon"], o["input_bg"], 0.1), o["input_bg"], 3.0),
        "send_btn": ensure_contrast(o["accent"], o["input_bg"], 3.0),
        "dialog_bg": o["surface"], "emoji_panel_bg": o["surface"],
        "button_bg": o["accent"],
        "switch_on": o["accent"], "switch_off": mix(o["text2"], o["bg"], 0.4), "checkbox": o["accent"],
        "tab_active": o["accent"], "progress": o["accent"],
        "story1": ensure_contrast(o["accent"], o["bg"], 3.0),
        "story2": ensure_contrast(accent2, o["bg"], 3.0),
        "story_close1": ensure_contrast("#3dd68c" if dark else "#2fa462", o["bg"], 3.0),
        "story_close2": ensure_contrast("#a3e635" if dark else "#5aa31f", o["bg"], 3.0),
        "chart_grid": mix(o["text2"], o["bg"], 0.78), "chart_text": o["text2"],
        **{k: ensure_contrast(from_hsl(h, clamp(to_hsl(o["accent"])[1], 0.55, 0.85), 0.62 if dark else 0.45),
                              o["bg"], 3.0) for k, h in CHART_HUES.items()},
        "error": ensure_contrast("#e5484d" if dark else "#d13438", o["bg"], 3.0),
        "success": ensure_contrast("#3dd68c" if dark else "#218358", o["bg"], 3.0),
    }
    for k, v in defaults.items():
        out.setdefault(k, v)
    late = {
        "badge_text": on_color(out["badge"], None, 4.5), "fab_icon": on_color(out["fab_bg"], None, 3.0),
        "menu_text": on_color(out["dialog_bg"], accent, 7.0),
        "menu_icon": ensure_contrast(mix(out["icon"], out["dialog_bg"], 0.1), out["dialog_bg"], 3.0),
        "button_text": on_color(out["button_bg"], None, 4.5),
    }
    for k, v in late.items():
        out.setdefault(k, v)
    return out


def fix_contrast(roles: dict, boost: float = 0.0, locked: dict | None = None) -> dict:
    """boost — усиление требований к контрасту (0.2 = на 20% строже), locked — роли, которые нельзя менять."""
    out = dict(roles)
    locked = locked or {}
    out.update(locked)
    for k in ROLE_KEYS:
        if k not in out or not isinstance(out[k], str) or not out[k].startswith("#"):
            out[k] = "#888888"
    spread_charts(out, locked)
    for _ in range(2):
        for fg, bg, ratio in CONTRAST_RULES:
            ratio = min(21.0, ratio * (1 + boost))
            if (fg, bg) not in BG_ONLY_RULES and fg not in locked:
                out[fg] = ensure_contrast(out[fg], effective(out, bg), ratio)
            if (contrast(out[fg], effective(out, bg)) < ratio - 0.01 and bg not in ("bg", "surface")
                    and bg not in locked):
                # текст уже предельный (почти белый/чёрный) — двигаем светлоту фона
                h, s, l = to_hsl(out[bg])
                away = -1 if luminance(out[fg]) > luminance(effective(out, bg)) else 1
                # полупрозрачный пузырь меняем мягко (остальное доберёт плотность ниже), сплошной — сколько нужно
                translucent = effective(out, bg) != out[bg]
                room = (l if away < 0 else 1 - l) * 0.5  # не больше половины пути до чёрного/белого
                steps = max(2, int(min(0.25, room) * 100)) if translucent else 60
                for i in range(1, steps):
                    cand = from_hsl(h, s, clamp(l + away * i * 0.01))
                    if contrast(out[fg], effective({**out, bg: cand}, bg)) >= ratio:
                        out[bg] = cand
                        break
                else:
                    out[bg] = from_hsl(h, s, clamp(l + away * (min(0.25, room) if translucent else 0.6)))
    # прозрачность слишком сильная для читаемости — понемногу уплотняем пузырь
    if out.get("_fx"):
        fx = sanitize_fx(out["_fx"])
        for fg, bg, ratio in CONTRAST_RULES:
            key = ALPHA_BG.get(bg)
            if not key:
                continue
            ratio = min(21.0, ratio * (1 + boost))
            while fx[key] < 100 and contrast(out[fg], effective({**out, "_fx": fx}, bg)) < ratio - 0.01:
                fx[key] = min(100, fx[key] + 5)
                if fg not in locked:
                    out[fg] = ensure_contrast(out[fg], effective({**out, "_fx": fx}, bg), ratio)
        out["_fx"] = fx
    return out


def contrast_report(roles: dict, boost: float = 0.0) -> list[dict]:
    rep = []
    for fg, bg, ratio in CONTRAST_RULES:
        ratio = round(min(21.0, ratio * (1 + boost)), 2)
        c = contrast(roles[fg], effective(roles, bg))
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


# ---------------- ИИ пишет тему целиком ----------------
def _roles_spec() -> str:
    return "\n".join(f"{g}: " + ", ".join(f"{k} ({ROLE_LABELS[k]})" for k in keys) for g, keys in ROLE_GROUPS)


FULL_SYSTEM = (
    "Ты — дизайнер тем для Telegram. Сам придумываешь цельную, уникальную и эстетичную тему: "
    "палитру, все цвета интерфейса, название и описание обоев. Все тексты должны легко читаться "
    "(основной текст ≥ 7:1 к фону, вторичный ≥ 4.5:1). Отвечаешь только JSON."
)


def ai_full_prompt(description: str, mode: str, palette: list[dict] | None = None) -> str:
    pal = (", ".join(p["hex"] for p in palette) if palette else "")
    return (
        f"Идея темы: {description or 'придумай сам что-то красивое и необычное'}\n"
        f"Режим: {mode} (auto — выбери сам)\n"
        + (f"Опирайся на палитру обоев пользователя: {pal}\n" if pal else "")
        + "Заполни ВСЕ роли цветами HEX #rrggbb:\n" + _roles_spec() + "\n\n"
        + "\nЭффекты fx (числа 0–100): " + _fx_spec() + "\n\n"
        'Формат: {"name": "красивое название 1–3 слова", "mode": "dark|light", '
        '"wallpaper_prompt": "подробное описание обоев на английском для нейросети-художника, без текста", '
        '"roles": {"bg": "#...", ... все роли ...}, "fx": {"in_alpha": 100, ...}}'
    )


def _fx_spec() -> str:
    return ("in_alpha/out_alpha — непрозрачность входящих/исходящих (100 = сплошной, 70 = «стекло»), "
            "service_alpha — плашки дат, input_alpha — панель ввода, selection_alpha — выделение, "
            "shadow_in/shadow_out — цвет тени #rrggbb, shadow_in_alpha/shadow_out_alpha — сила тени (0 = нет), "
            "animated_gradient — true/false (переливающийся градиент исходящих)")


def _hex_roles(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        if k in ROLE_KEYS and isinstance(v, str) and re.fullmatch(r"#?[0-9a-fA-F]{6}", v.strip()):
            out[k] = "#" + v.strip().lstrip("#").lower()
    return out


def normalize_full(data: dict, palette: list[dict] | None = None, boost: float = 0.0,
                   locked: dict | None = None) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Нейросеть вернула не то — попробуй ещё раз")
    roles = _hex_roles(data.get("roles") or data.get("colors") or {})
    if len(roles) < 4:
        raise ValueError("Нейросеть не прислала цвета темы — попробуй ещё раз или выбери другую нейросеть")
    if "bg" not in roles:
        roles["bg"] = build_theme(palette or [{"hex": roles.get("accent", "#8f7bff"), "share": 1}],
                                  data.get("mode", "auto"))["bg"]
    base = derive_roles({**roles, **(locked or {})})
    base["_fx"] = sanitize_fx(data.get("fx") if isinstance(data.get("fx"), dict) else {})
    full = fix_contrast(base, boost, locked)
    full["_fx"] = base["_fx"]
    full["_meta"] = {"mode": "dark" if luminance(full["bg"]) < 0.3 else "light", "style": "ai-full",
                     "name": str(data.get("name") or "AI тема")[:40],
                     "filled_by_ai": len(roles), "total": len(ROLE_KEYS)}
    return {"roles": full, "wallpaper_prompt": str(data.get("wallpaper_prompt") or "")[:600]}


EDIT_SYSTEM = ("Ты дорабатываешь тему Telegram по просьбе пользователя. Меняешь только нужные цвета, "
               "сохраняя читаемость текста. Отвечаешь только JSON.")


def ai_edit_prompt(roles: dict, instruction: str) -> str:
    cur = {k: roles[k] for k in ROLE_KEYS if k in roles}
    return (
        f"Текущая тема (роль → цвет):\n{json.dumps(cur, ensure_ascii=False)}\n"
        f"Текущие эффекты fx: {json.dumps(sanitize_fx(roles.get('_fx')), ensure_ascii=False)}\n\n"
        f"Значения ролей:\n{_roles_spec()}\nЭффекты: {_fx_spec()}\n\n"
        f"Просьба: {instruction}\n\n"
        "Линии статистики (chart_*) должны оставаться разными по цвету и контрастными к фону (≥ 3:1); "
        "просят раскрасить статистику — меняй все 10 линий.\n"
        "«Стеклянные/прозрачные сообщения» — это fx.in_alpha И fx.out_alpha (60–80), а не одна сторона; "
        "«тень» — shadow_in_alpha и shadow_out_alpha (15–45). Истории — story1/story2, близкие друзья — story_close1/2.\n"
        "comment пиши по-русски.\n"
        'Верни только изменённое: {"roles": {"роль": "#rrggbb", ...}, "fx": {"параметр": значение, ...}, '
        '"comment": "что изменил, 1 фраза"}'
    )


def apply_edit(roles: dict, data: dict, boost: float = 0.0, locked: dict | None = None,
               instruction: str = "") -> tuple[dict, list[str], str]:
    if instruction:
        data = complete_edit(roles, data, instruction, locked)
    changes = _hex_roles((data or {}).get("roles") or {})
    new = dict(roles)
    new.update(changes)
    fx_changes = (data or {}).get("fx") or {}
    if isinstance(fx_changes, dict) and fx_changes:
        new["_fx"] = sanitize_fx({**(roles.get("_fx") or {}), **fx_changes})
        changes = {**changes, **{f"fx.{k}": v for k, v in fx_changes.items() if k in FX_DEFAULT}}
    fixed = fix_contrast(new, boost, locked)  # в _fx может поднять непрозрачность ради читаемости
    for k in ("_meta", "_overrides"):
        if k in new:
            fixed[k] = new[k]
    return fixed, sorted(changes), str((data or {}).get("comment") or "")[:200]
