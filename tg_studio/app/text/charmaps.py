"""Таблицы «шрифтов» Unicode и наборы замен букв — общие для языков и текстов постов."""
from __future__ import annotations

import string

UPPER = string.ascii_uppercase
LOWER = string.ascii_lowercase
DIGITS = string.digits


def _math(upper: int | None, lower: int | None, digits: int | None = None, exceptions: dict | None = None) -> dict:
    m = {}
    if upper is not None:
        m.update({c: chr(upper + i) for i, c in enumerate(UPPER)})
    if lower is not None:
        m.update({c: chr(lower + i) for i, c in enumerate(LOWER)})
    if digits is not None:
        m.update({c: chr(digits + i) for i, c in enumerate(DIGITS)})
    m.update(exceptions or {})
    return m


def _pairs(src: str, dst: list[str] | str) -> dict:
    return {s: d for s, d in zip(src, dst) if d}


FONTS: dict[str, dict] = {
    "bold": {"label": "𝐁𝐨𝐥𝐝", "map": _math(0x1D400, 0x1D41A, 0x1D7CE)},
    "italic": {"label": "𝐼𝑡𝑎𝑙𝑖𝑐", "map": _math(0x1D434, 0x1D44E, None, {"h": "ℎ"})},
    "bold_italic": {"label": "𝑩𝒐𝒍𝒅 𝑰𝒕𝒂𝒍𝒊𝒄", "map": _math(0x1D468, 0x1D482)},
    "sans": {"label": "𝖲𝖺𝗇𝗌", "map": _math(0x1D5A0, 0x1D5BA, 0x1D7E2)},
    "sans_bold": {"label": "𝗦𝗮𝗻𝘀 𝗕𝗼𝗹𝗱", "map": _math(0x1D5D4, 0x1D5EE, 0x1D7EC)},
    "sans_italic": {"label": "𝘚𝘢𝘯𝘴 𝘐𝘵𝘢𝘭𝘪𝘤", "map": _math(0x1D608, 0x1D622)},
    "sans_bold_italic": {"label": "𝙎𝙖𝙣𝙨 𝘽𝙤𝙡𝙙 𝙄", "map": _math(0x1D63C, 0x1D656)},
    "mono": {"label": "𝙼𝚘𝚗𝚘", "map": _math(0x1D670, 0x1D68A, 0x1D7F6)},
    "script": {"label": "𝓢𝓬𝓻𝓲𝓹𝓽", "map": _math(0x1D4D0, 0x1D4EA)},
    "fraktur": {"label": "𝕱𝖗𝖆𝖐𝖙𝖚𝖗", "map": _math(0x1D56C, 0x1D586)},
    "double": {"label": "𝔻𝕠𝕦𝕓𝕝𝕖", "map": _math(0x1D538, 0x1D552, 0x1D7D8, {
        "C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"})},
    "small_caps": {"label": "sᴍᴀʟʟ ᴄᴀᴘs", "map": _pairs(LOWER, "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ")},
    "superscript": {"label": "ˢᵘᵖᵉʳ", "map": {**_pairs(LOWER, list("ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻ")),
                                               **_pairs(UPPER, list("ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᵠᴿˢᵀᵁⱽᵂˣʸᶻ")),
                                               **_pairs(DIGITS, "⁰¹²³⁴⁵⁶⁷⁸⁹")}},
    "subscript_digits": {"label": "₁₂₃", "map": _pairs(DIGITS, "₀₁₂₃₄₅₆₇₈₉")},
    "circled": {"label": "ⓒⓘⓡⓒⓛⓔ", "map": {**_math(0x24B6, 0x24D0), **_pairs(DIGITS, "⓪①②③④⑤⑥⑦⑧⑨")}},
    "neg_circled": {"label": "🅒🅘🅡🅒🅛🅔", "map": {**_math(0x1F150, None), **{c: chr(0x1F150 + i) for i, c in enumerate(LOWER)}}},
    "squared": {"label": "🅂🅀🅄🄰🅁🄴", "map": {**_math(0x1F130, None), **{c: chr(0x1F130 + i) for i, c in enumerate(LOWER)}}},
    "neg_squared": {"label": "🆂🆀🆄🅰🆁🅴", "map": {**_math(0x1F170, None), **{c: chr(0x1F170 + i) for i, c in enumerate(LOWER)}}},
    "fullwidth": {"label": "Ｗｉｄｅ", "map": _math(0xFF21, 0xFF41, 0xFF10)},
    "aesthetic": {"label": "ᥲᥱ᥉thᥱtᎥᥴ", "map": _pairs(LOWER, list("ᥲbᥴdᥱfghᎥjkᥣ꧑ᥒ᥆pqr᥉tᥙvᥕxyz"))},
    "aesthetic2": {"label": "ꪖꫀ𝘴ꪻꫝꫀꪻ꠸ᥴ", "map": _pairs(LOWER, list("ꪖ᥇ᥴᦔꫀᠻᧁꫝ꠸꠹ᛕꪶꪑꪀꪮρ𝘲𝘳𝘴ꪻꪊꪜ᭙᥊ꪗɀ"))},
    "bold_numbers": {"label": "𝟭𝟮𝟯", "map": _pairs(DIGITS, [chr(0x1D7EC + i) for i in range(10)])},
    # ---- кириллица ----
    "cyr_greek": {"label": "Кириллица → αβεκ", "map": _pairs("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                  ["α", "б", "β", "г", "∂", "ε", "ë", "ж", "з", "υ", "ύ", "κ", "λ", "м", "η", "σ", "π", "ρ", "ς", "τ",
                   "γ", "φ", "χ", "ц", "ч", "ш", "щ", "ъ", "ы", "ь", "э", "ю", "я"])},
    "cyr_soft": {"label": "Кириллица → ᥲᥱ᥆ᥴ", "map": _pairs("аеосрухкнмтвиёэ",
                 ["ᥲ", "ᥱ", "᥆", "ᥴ", "ρ", "ᥡ", "᥊", "κ", "н", "ꮇ", "т", "ʙ", "ᥙ", "ᥱ̈", "϶"])},
    "cyr_small_caps": {"label": "Кириллица → ᴀʙᴇᴋ", "map": _pairs("авекмнорстух",
                       ["ᴀ", "ʙ", "ᴇ", "ᴋ", "ᴍ", "ʜ", "ᴏ", "ᴘ", "ᴄ", "ᴛ", "ʏ", "x"])},
}

COMBINING = {
    "strike": "̶", "underline": "̲", "double_underline": "̳", "slash": "̸",
    "overline": "̅", "dots_below": "̤", "wave": "̰", "x_above": "̽",
}


def apply_font(text: str, font: str) -> str:
    m = FONTS.get(font, {}).get("map", {})
    has_upper = any(k.isupper() for k in m)
    out = []
    for c in text:
        if c in m:
            out.append(m[c])
        elif not has_upper and c.lower() in m:
            out.append(m[c.lower()])
        else:
            out.append(c)
    return "".join(out)


def apply_combining(text: str, mark: str) -> str:
    ch = COMBINING.get(mark, mark)
    return "".join(c + ch if not c.isspace() else c for c in text)


def parse_custom_map(text: str) -> dict:
    """Строки вида 'а=ᥲ' или 'а ᥲ' → словарь замен (регистр учитывается)."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            k, v = parts[0], parts[1]
        if k:
            out[k] = v
    return out


def charmap_table() -> dict:
    return {k: {"label": v["label"], "map": v["map"]} for k, v in FONTS.items()}
