"""Генератор языков Telegram: замена символов / переписывание нейросетью
с защитой плейсхолдеров (%1$s, {count}, %@, **, \\n, <b>, un1 …) и экспорт файлов."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .. import rules
from ..ai.providers import AIClient
from ..text.charmaps import FONTS

PLATFORMS = {
    "android": "Android",
    "ios": "iPhone / iPad",
    "tdesktop": "Telegram Desktop (Windows / Linux)",
    "macos": "macOS",
    "android_x": "Telegram X (Android)",
}

PLACEHOLDER_RE = re.compile(
    r"%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[sdifuxXc@]"   # printf / iOS
    r"|%%"
    r"|\{[^{}\n]{1,40}\}"                               # {count} {user}
    r"|<[^<>\n]{1,80}>"                                 # html-теги
    r"|\*\*|__|~~|\|\|"                                 # markdown-маркеры
    r"|\\n|\n|\\\"|\\'"                                 # переводы строк и экранирование
    r"|\bun\d\b"                                        # android un1/un2
    r"|https?://\S+|@\w+"                               # ссылки, юзернеймы
    r"|\[[^\[\]\n]{0,3}\]"                              # [a] [/a]
)

PREVIEW_KEYS = {
    "android": ["AppName", "Chats", "Contacts", "Calls", "Settings", "SavedMessages", "Search", "TypeMessage",
                "Online", "NewGroup", "NewChannel", "ArchivedChats", "Send", "Cancel", "Forward", "Reply"],
    "ios": ["DialogList.Title", "Contacts.Title", "Calls.TabTitle", "Settings.Title", "DialogList.SavedMessages",
            "Common.Search", "Conversation.InputTextPlaceholder", "Presence.online", "Compose.NewGroup",
            "Compose.NewChannel", "Common.Cancel", "Conversation.ContextMenuReply", "Conversation.ContextMenuForward"],
    "tdesktop": ["lng_dlg_filter", "lng_settings_title", "lng_menu_contacts", "lng_menu_calls", "lng_saved_messages",
                 "lng_message_ph", "lng_status_online", "lng_create_group_title", "lng_create_channel_title",
                 "lng_archived_name", "lng_context_reply_msg", "lng_context_forward_msg", "lng_cancel", "lng_send_button"],
    "macos": ["DialogList.Title", "Settings.Title", "Contacts.Title", "Presence.online"],
    "android_x": ["Chats", "Contacts", "Settings", "Search"],
}


def split_protected(text: str) -> list[tuple[bool, str]]:
    parts, pos = [], 0
    for m in PLACEHOLDER_RE.finditer(text):
        if m.start() > pos:
            parts.append((False, text[pos:m.start()]))
        parts.append((True, m.group(0)))
        pos = m.end()
    if pos < len(text):
        parts.append((False, text[pos:]))
    return parts


def placeholders(text: str) -> Counter:
    return Counter(m.group(0) for m in PLACEHOLDER_RE.finditer(text))


def apply_map(text: str, mapping: dict, case_fallback: bool = True) -> str:
    def tr(seg: str) -> str:
        # многосимвольные ключи (например «ой=ꭷ») обрабатываем первыми
        multi = sorted((k for k in mapping if len(k) > 1), key=len, reverse=True)
        out, i = [], 0
        while i < len(seg):
            for k in multi:
                if seg.startswith(k, i):
                    out.append(mapping[k])
                    i += len(k)
                    break
            else:
                c = seg[i]
                if c in mapping:
                    out.append(mapping[c])
                elif case_fallback and c.lower() in mapping:
                    out.append(mapping[c.lower()])
                else:
                    out.append(c)
                i += 1
        return "".join(out)
    return "".join(seg if prot else tr(seg) for prot, seg in split_protected(text))


def build_mapping(presets: list[str], custom: dict | None = None) -> dict:
    m: dict = {}
    for p in presets:
        m.update(FONTS.get(p, {}).get("map", {}))
    m.update(custom or {})
    return m


def flatten(entries: list[dict]) -> dict[str, str]:
    flat = {}
    for e in entries:
        if "plural" in e:
            for form, v in e["plural"].items():
                flat[f"{e['key']}#{form}"] = v
        else:
            flat[e["key"]] = e["value"]
    return flat


def unflatten(flat: dict[str, str], template: list[dict]) -> list[dict]:
    out = []
    for e in template:
        if "plural" in e:
            out.append({"key": e["key"], "plural": {f: flat.get(f"{e['key']}#{f}", v) for f, v in e["plural"].items()}})
        else:
            out.append({"key": e["key"], "value": flat.get(e["key"], e["value"])})
    return out


def select_entries(entries: list[dict], key_filter: str = "", limit: int = 0) -> list[dict]:
    if key_filter:
        rx = re.compile(key_filter, re.I)
        entries = [e for e in entries if rx.search(e["key"]) or rx.search(e.get("value", "") or "")]
    if limit:
        entries = entries[:limit]
    return entries


AI_SYSTEM = (
    "Ты локализатор интерфейса Telegram. Переписываешь строки интерфейса в заданном стиле. "
    "ЖЁСТКИЕ ПРАВИЛА: 1) все плейсхолдеры и служебные последовательности (%1$s, %d, %@, {count}, {user}, "
    "**, __, \\n, <b>, </b>, un1, [a], ссылки) сохраняй символ-в-символ и в том же количестве; "
    "2) строка должна оставаться понятной как элемент интерфейса (кнопки — короткие); "
    "3) не добавляй переводы строк; 4) верни JSON-объект с теми же ключами."
)


async def ai_rewrite(job, flat: dict[str, str], description: str, target_lang: str, ai: AIClient,
                     batch_size: int = 40, fallback_map: dict | None = None, examples: str = "") -> dict[str, str]:
    keys = list(flat)
    growth = rules.lang_max_growth()  # правило: насколько строка может стать длиннее (0 = без ограничения)
    result: dict[str, str] = {}
    total = len(keys)
    bad = 0
    for i in range(0, total, batch_size):
        chunk = {k: flat[k] for k in keys[i:i + batch_size]}
        prompt = (f"Стиль языка: {description}\n"
                  f"Язык результата: {target_lang}\n"
                  + (f"Примеры желаемого оформления: {examples}\n" if examples else "")
                  + "Строки (JSON, ключ → текст):\n" + json.dumps(chunk, ensure_ascii=False))
        try:
            data = await ai.chat_json(prompt, system=AI_SYSTEM, max_tokens=8000)
        except Exception as e:  # noqa: BLE001
            job.update(message=f"Пачка {i // batch_size + 1}: ошибка ИИ ({e}), оставляю исходник")
            data = {}
        for k, orig in chunk.items():
            new = data.get(k) if isinstance(data, dict) else None
            too_long = growth > 0 and isinstance(new, str) and len(new) > len(orig) * (1 + growth) + 2
            if isinstance(new, str) and new.strip() and placeholders(new) == placeholders(orig) and not too_long:
                result[k] = new
            else:
                if new is not None:
                    bad += 1
                result[k] = apply_map(orig, fallback_map) if fallback_map else orig
        job.update((i + len(chunk)) / total, f"ИИ: {min(i + batch_size, total)}/{total} строк"
                   + (f" (исправлено плейсхолдеров: {bad})" if bad else ""))
    return result


# ---------------- экспорт ----------------
IOS_PLURAL = {"zero": "_0", "one": "_1", "two": "_2", "few": "_3_10", "many": "_many", "other": "_any"}


def _esc_strings(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _esc_android(v: str) -> str:
    v = xml_escape(v)
    v = v.replace("'", "\\'").replace('"', '\\"').replace("\n", "\\n")
    return v


def export_platform(entries: list[dict], platform: str) -> tuple[str, str]:
    """→ (имя файла, содержимое)."""
    if platform in ("android", "android_x"):
        lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
        for e in entries:
            if "plural" in e:
                for f, v in e["plural"].items():
                    lines.append(f'    <string name="{e["key"]}_{f}">{_esc_android(v)}</string>')
            else:
                lines.append(f'    <string name="{e["key"]}">{_esc_android(e["value"])}</string>')
        lines.append("</resources>")
        return "strings.xml", "\n".join(lines) + "\n"
    lines = []
    for e in entries:
        if "plural" in e:
            for f, v in e["plural"].items():
                key = f"{e['key']}#{f}" if platform == "tdesktop" else f"{e['key']}{IOS_PLURAL.get(f, '_' + f)}"
                lines.append(f'"{key}" = "{_esc_strings(v)}";')
        else:
            lines.append(f'"{e["key"]}" = "{_esc_strings(e["value"])}";')
    name = "lang.strings" if platform == "tdesktop" else "Localizable.strings"
    return name, "\n".join(lines) + "\n"


def save_language(out_dir: Path, name: str, per_platform: dict[str, list[dict]]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for platform, entries in per_platform.items():
        fname, content = export_platform(entries, platform)
        p = out_dir / f"{name}_{platform}_{fname}"
        p.write_text(content, "utf-8")
        (out_dir / f"{name}_{platform}.json").write_text(json.dumps(entries, ensure_ascii=False), "utf-8")
        files[platform] = str(p)
    return files


def preview(entries: list[dict], platform: str) -> dict:
    flat = {e["key"]: e.get("value") or next(iter(e.get("plural", {}).values()), "") for e in entries}
    keys = PREVIEW_KEYS.get(platform, [])
    return {k: flat[k] for k in keys if k in flat}
