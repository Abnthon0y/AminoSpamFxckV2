"""Правила пользователя для всех разделов.

Каждый раздел имеет:
  • text — свободные правила для нейросети (добавляются в системный промпт всех запросов раздела);
  • «жёсткие» поля — программа соблюдает их сама, даже без ИИ.
Наборы правил (presets) можно сохранять и переключать.
"""
from __future__ import annotations

import copy
import json
import re
import threading

from .config import DATA_DIR

RULES_FILE = DATA_DIR / "rules.json"
SECTIONS = ["general", "themes", "lang", "emoji", "pixel", "stickers", "text"]
SECTION_LABELS = {"general": "Общие", "themes": "Темы", "lang": "Языки", "emoji": "Эмодзи-паки",
                  "pixel": "Пиксель-GIF", "stickers": "Стикеры", "text": "Тексты постов"}

DEFAULT_RULES: dict = {
    "general": {"text": "", "ai_lang": "", "banned": ""},
    "themes": {"text": "", "mode": "", "contrast_boost": 0, "locked": "", "styles": []},
    "lang": {"text": "", "replace": "", "keys": "", "prefix": "", "suffix": "", "max_growth": 0},
    "emoji": {"text": "", "default_emoji": "", "remove_bg": "auto", "banner_max_w": 4, "tall_max_h": 4,
              "hearts_bw": True, "font": "", "banner_colors": ""},
    "pixel": {"text": "", "palette": "", "outline_color": ""},
    "stickers": {"text": "", "default_emoji": ""},
    "text": {"text": "", "replace": "", "banned": "", "header": "", "signature": "", "width": 0},
}

_lock = threading.Lock()


def _merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _read() -> dict:
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text("utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def load() -> dict:
    with _lock:
        stored = _read()
    return {"rules": _merge(DEFAULT_RULES, stored.get("rules", {})), "presets": stored.get("presets", {}),
            "active": stored.get("active", "")}


def save(rules: dict | None = None, presets: dict | None = None, active: str | None = None) -> dict:
    cur = load()
    if rules is not None:
        cur["rules"] = _merge(DEFAULT_RULES, rules)
    if presets is not None:
        cur["presets"] = presets
    if active is not None:
        cur["active"] = active
    with _lock:
        RULES_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=1), "utf-8")
    return cur


def section(name: str) -> dict:
    return load()["rules"].get(name, {})


# ---------------- для нейросети ----------------
def prompt_block(name: str) -> str:
    r = load()["rules"]
    g, s = r["general"], r.get(name, {})
    lines = []
    if g.get("ai_lang"):
        lines.append(f"Язык ответов: {g['ai_lang']}.")
    if g.get("text", "").strip():
        lines.append(g["text"].strip())
    if g.get("banned", "").strip():
        lines.append(f"Никогда не используй: {g['banned'].strip()}")
    if s.get("text", "").strip():
        lines.append(s["text"].strip())
    if name == "text" and s.get("banned", "").strip():
        lines.append(f"Не используй в тексте: {s['banned'].strip()}")
    if name == "pixel" and s.get("palette", "").strip():
        lines.append(f"Используй только цвета: {s['palette'].strip()}")
    if not lines:
        return ""
    return "\n\nПРАВИЛА ПОЛЬЗОВАТЕЛЯ (обязательны и важнее остальных пожеланий):\n" + "\n".join(f"- {x}" for x in lines)


def with_rules(system: str | None, name: str | None) -> str | None:
    if not name:
        return system
    block = prompt_block(name)
    if not block:
        return system
    return (system or "") + block


# ---------------- разбор ----------------
def parse_pairs(text: str, sep: str = "=>") -> list[tuple[str, str]]:
    """Строки «старое => новое» (также принимается «=» и «→»)."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for s in (sep, "→", "="):
            if s in line:
                a, b = line.split(s, 1)
                if a.strip():
                    out.append((a.strip(), b.strip()))
                break
    return out


def banned_chars(*texts: str) -> list[str]:
    items = []
    for t in texts:
        items += [x for x in re.split(r"[\s,]+", t or "") if x]
    return items


def remove_banned(text: str, banned: list[str]) -> str:
    for b in sorted(banned, key=len, reverse=True):
        text = text.replace(" " + b + " ", " ").replace(" " + b, "").replace(b, "")
    return text


def replace_words(text: str, pairs: list[tuple[str, str]]) -> str:
    for a, b in pairs:
        if re.fullmatch(r"[\w\- ]+", a, re.U):
            text = re.sub(rf"(?<!\w){re.escape(a)}(?!\w)", b, text)
        else:
            text = text.replace(a, b)
    return text


# ---------------- тексты ----------------
def apply_text(text: str, full_post: bool = True) -> str:
    r = load()["rules"]
    s, g = r["text"], r["general"]
    text = replace_words(text, parse_pairs(s.get("replace", "")))
    text = remove_banned(text, banned_chars(s.get("banned", ""), g.get("banned", "")))
    if full_post:
        head, sig = s.get("header", "").strip(), s.get("signature", "").strip()
        if head and not text.lstrip().startswith(head):
            text = head + "\n" + text
        if sig and not text.rstrip().endswith(sig):
            text = text.rstrip() + "\n" + sig
    return text


# ---------------- темы ----------------
def theme_locked() -> dict[str, str]:
    out = {}
    for k, v in parse_pairs(section("themes").get("locked", ""), "="):
        v = v.strip()
        if re.fullmatch(r"#?[0-9a-fA-F]{6}", v):
            out[k.strip()] = "#" + v.lstrip("#").lower()
    return out


# ---------------- языки ----------------
def lang_pre(flat: dict[str, str], split_protected) -> dict[str, str]:
    """До преобразования: замены слов «Чаты => Мурчатики» по исходному тексту (плейсхолдеры не трогаем)."""
    pairs = parse_pairs(section("lang").get("replace", ""))
    if not pairs:
        return flat
    return {k: "".join(seg if prot else replace_words(seg, pairs) for prot, seg in split_protected(v))
            for k, v in flat.items()}


def lang_post(flat: dict[str, str], split_protected) -> dict[str, str]:
    """После преобразования: запрещённые символы, приставка/окончание, точные значения по ключам."""
    s = section("lang")
    keys = dict(parse_pairs(s.get("keys", "")))
    banned = banned_chars(section("general").get("banned", ""))
    pre, suf = s.get("prefix", ""), s.get("suffix", "")
    out = {}
    for k, v in flat.items():
        base_key = k.split("#")[0]
        if k in keys or base_key in keys:
            out[k] = keys.get(k, keys.get(base_key))
            continue
        if banned:
            v = "".join(seg if prot else remove_banned(seg, banned) for prot, seg in split_protected(v))
        if v.strip() and (pre or suf):
            v = f"{pre}{v}{suf}"
        out[k] = v
    return out


def lang_max_growth() -> float:
    return float(section("lang").get("max_growth") or 0) / 100


# ---------------- эмодзи ----------------
def apply_emoji_item(it: dict) -> dict:
    s = section("emoji")
    mode = s.get("remove_bg", "auto")
    if mode == "always" and it.get("kind") not in ("banner", "tall", "text", "spacer", "collage"):
        it["remove_bg"] = True
        it["fit"] = "contain"
    elif mode == "never":
        it["remove_bg"] = False
    if it.get("kind") == "banner":
        it["w"] = min(int(it.get("w", 2)), max(2, int(s.get("banner_max_w") or 4)))
    if it.get("kind") == "tall":
        it["h"] = min(int(it.get("h", 2)), max(2, int(s.get("tall_max_h") or 4)))
    if it.get("kind") == "heart" and s.get("hearts_bw", True):
        it["bw"] = True
    if s.get("default_emoji") and it.get("emoji") in (None, "", "✨"):
        it["emoji"] = s["default_emoji"]
    return it


# ---------------- пиксели ----------------
def pixel_palette() -> list[tuple[int, int, int]]:
    cols = re.findall(r"#?([0-9a-fA-F]{6})\b", section("pixel").get("palette", ""))
    return [tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) for c in cols]
