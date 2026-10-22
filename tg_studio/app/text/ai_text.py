"""Нейросеть для эстетичного оформления текстов постов, ников и био."""
from __future__ import annotations

from ..ai.providers import AIClient

STYLE_EXAMPLES = {
    "soft": ("нежный / милый (soft, coquette)",
             "𓏲·˚🦴🧠 𖦆 𝗸𝗶𝗺 𝘀𝗲𝗼𝗸 𝗷𝗶𝗻 ¡! ⋆ ࣪. 🎀.\n"
             "🩰⋆ Ꮺ ָ࣪  ۰ 𝗪𝗼𝗿𝗹𝗱𝘄𝗶𝗱𝗲 𝗵𝗮𝗻𝗱𝘀𝗼𝗺𝗲 ❜  ࣪🧠،،̲ ✶\n"
             "୨𖩒   ׅ    ׂ   🎀̷    𝟷𝟷𝟷    〭   ⬯\nɛɜ   𝗉𝗂𝗇𝗄   𝖽𝖾𝗅𝗂𝖼𝖺𝗍𝖾   𝗁𝖾𝖺𝗋𝗍."),
    "dark": ("тёмный / готик / гранж",
             "🔪 ٫   (𝐘̸̶)   ✶  𝐒̷☹︎𝐖𝕺𝐍̸    𒉺  私 !\n"
             "۰ ⸂ぬ  ࣪˖⁩ 𝗚𝟏𝐑𝐋🅲✸🆁🅴 ⋆ ࣪ 🕷 !\n"
             "᭝ ܰ ៳ׄ  ֢ ⛓ ˖ ʝᧉ𐐫֪͞𝖞ׄ 𓄳 ̤◞ 𝚖𐐼ׄ͟𝗸𝗻𐐼۫℮ִֶָ  𖤐ֹ"),
    "minimal": ("минимализм, воздух, тонкие символы",
                "_ _\n        ྀི 　     name 　age 　prn   ᛝ\n        age 　⸝⸝ 　 𐙚 　` quote ` 　( ´ ▽ ` ) 𓈒\n_ _\n"
                "⪩⪩ㅤ ㅤ𝗍𝗈𝗋𝗍𝗂𝗇𝗁⍺ㅤ ㅤ𝖽𝖾ㅤ ㅤ¡!"),
    "kpop": ("k-pop / стэн-аккаунт",
             "♟ꫂ 最 𝕥𝕒𝕖𝕙𝕪𝕦𝕟𝕘 🧸𓂅\n⌗ 🎨 𝘁𝗮𝗲 𖧵 𝟭𝟵𝟵𝟱 🎭𓂅\n𓄹𓈒🥛 𓏲 ๋ ۰𝕁𝕖𝕠𝕟🌷; ᕱ"),
    "cottage": ("коттеджкор / деревня / фермa",
                "𓏲  🧺 👩🏻‍🌾 𓂃 ✦ 🌷 ˒\n𓏲  🍯 🧺 𓂃 ✦ 🐝 ˒\n𓏲  🍓 🏡 𓂃 ✦ 🧸 ˒"),
    "sparkle": ("плотная россыпь символов (стена блёсток)",
                "⊹    ۪  𖥔  ˑ  ִ  ֗    ִ  ۫   ˑ  𖥻 ִ ۫  ּ   ﹗ ˖  ་ 💭 𖦆    ֺ  ָ   ֙⋆\n"
                "• ˖ ࣪𖦆 ˓ 🥛 ★ ﹆ׂׂ ˖ ◗    ᥫ᭡   ˖ ࣪ ‹ 𖥔 ࣪ ˖ ぅ  ་    ᳝   ◝     𖥻"),
    "y2k": ("y2k / киберкавай",
            "ଘ( ˊ♡ˋ )ଓ    𝙲𝚈𝙱𝙴𝚁   ♡︎⃚    𝙼𝙰𝙳͜͡𝙳𝙸𝙴    ⑇   🎀̸\n🎀⃞̷̵      𝚃𝙸𝙽𝚈    ♡⃕    𝙰𝙽͜͡𝙽𝙴      ⑇"),
    "frame": ("рамки и разделители",
              "╭─► ೃ♡\n╰───────────────────\n୨୧・┈・♡・┈・୨୧\n‧˚₊•┈┈┈┈ ᧔ෆ᧓ ┈┈┈┈•‧₊˚⊹"),
}

SYSTEM = (
    "Ты — дизайнер эстетичных текстов для Telegram-каналов (стиль Pinterest/aesthetic). "
    "Оформляешь текст декоративными Unicode-символами (˖ ࣪ ⊹ 𓂃 ୨୧ ꒰ ꒱ ⌗ ✦ ᵎ ♡ 𖥔 ִֶָ), "
    "стилизованными шрифтами (𝗯𝗼𝗹𝗱, 𝘪𝘵𝘢𝘭𝘪𝘤, 𝚖𝚘𝚗𝚘, ᴄᴀᴘs), каомодзи (૮₍ ˶ᵔ ᵕ ᵔ˶ ₎ა) и тематическими эмодзи. "
    "Главное: текст остаётся ЧИТАЕМЫМ — смысловые слова не замусоривай, декор вокруг и между блоками. "
    "Основной текст пиши обычными буквами на языке пользователя; стилизованный шрифт — только для заголовка "
    "из 1–3 слов; никогда не транслитерируй слова латиницей и не выдумывай слов. "
    "Соблюдай максимальную ширину строки. Не используй markdown, не добавляй пояснений — "
    "выдай только готовый текст."
)


def _style_block(style: str) -> str:
    name, ex = STYLE_EXAMPLES.get(style, STYLE_EXAMPLES["soft"])
    return f"Стиль: {name}\nПример такого оформления:\n{ex}\n"


async def run(action: str, payload: dict, ai: AIClient | None = None) -> str | list:
    ai = ai or AIClient()
    width = int(payload.get("width") or 32)
    style = payload.get("style", "soft")
    symbols = payload.get("symbols", "")
    emojis = payload.get("emojis", "")
    extra = payload.get("extra", "")
    common = (_style_block(style)
              + f"Максимальная ширина строки: {width} символов.\n"
              + (f"Обязательно используй эти символы: {symbols}\n" if symbols else "")
              + (f"Эмодзи-набор: {emojis}\n" if emojis else "")
              + (f"Дополнительно: {extra}\n" if extra else ""))
    if action == "post":
        prompt = (common + f"Напиши эстетичный пост для Telegram на тему: «{payload.get('topic', '')}». "
                  f"Язык: {payload.get('lang', 'русский')}. Структура: декоративная шапка, 2–4 коротких абзаца "
                  "или список с маркерами, разделитель, подпись/хэштеги.")
        return await ai.chat(prompt, system=SYSTEM, max_tokens=2000)
    if action == "post_content":
        # надёжный режим: ИИ пишет только смысл, оформление собирает программа
        prompt = (f"Напиши содержание поста для Telegram на тему: «{payload.get('topic', '')}». "
                  f"Язык: {payload.get('lang', 'русский')}. Обычный живой текст, без декоративных символов и "
                  "без «шрифтов», короткие фразы."
                  + (f" Дополнительно: {extra}." if extra else "")
                  + '\nОтвет JSON: {"title": "заголовок 1–4 слова", "intro": "1–2 предложения", '
                  '"points": ["3–5 коротких пунктов"], "outro": "финальная фраза", '
                  '"tags": ["2–4 хэштега без #"], "emojis": ["3–5 подходящих эмодзи"]}')
        data = await ai.chat_json(prompt, system="Ты автор коротких тёплых постов для Telegram. Отвечаешь только JSON.")
        return {k: data.get(k) for k in ("title", "intro", "points", "outro", "tags", "emojis")}
    if action == "decorate":
        prompt = (common + "Оформи этот текст, НЕ меняя слов (можно менять регистр/шрифт заголовка, "
                  "добавлять маркеры, разделители и декор):\n\n" + payload.get("text", ""))
        return await ai.chat(prompt, system=SYSTEM, max_tokens=2500)
    if action == "nicks":
        n = int(payload.get("count", 12))
        prompt = (common + f"Придумай {n} эстетичных вариантов ника/подписи для имени «{payload.get('topic', '')}». "
                  'Ответ JSON: {"items": ["...", "..."]}')
        data = await ai.chat_json(prompt, system=SYSTEM)
        return [str(x) for x in data.get("items", [])][:n]
    if action == "bio":
        prompt = (common + f"Сделай эстетичное био/шапку профиля. Данные: {payload.get('topic', '')}. "
                  "3–6 строк, можно шаблон name / age / prn / quote.")
        return await ai.chat(prompt, system=SYSTEM, max_tokens=1200)
    if action == "divider":
        n = int(payload.get("count", 8))
        prompt = (common + f"Придумай {n} разных эстетичных разделителей ровно по {width} символов шириной. "
                  'Ответ JSON: {"items": ["...", "..."]}')
        data = await ai.chat_json(prompt, system=SYSTEM)
        return [str(x) for x in data.get("items", [])][:n]
    raise ValueError(f"Неизвестное действие: {action}")
