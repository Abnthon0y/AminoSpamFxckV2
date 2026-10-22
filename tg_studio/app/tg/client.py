"""Работа с аккаунтом Telegram через Telethon (MTProto) и с Bot API.

Что умеет:
  • вход по номеру + код + (опционально) пароль 2FA, сессия сохраняется в data/
  • загрузка темы-файла (.attheme / .tdesktop-theme / .tgios-theme) и создание облачной темы
  • создание кросс-платформенной облачной темы из настроек (акцент + цвета сообщений + обои)
  • выгрузка исходных строк языка (android / ios / tdesktop / macos) для генератора языков
  • создание набора стикеров / эмодзи от имени аккаунта или через своего бота
"""
from __future__ import annotations

import json
import mimetypes
import re
import secrets
from pathlib import Path

import httpx

from ..config import DATA_DIR, load_settings

LANGPACK_CACHE = DATA_DIR / "langpacks"
LANGPACK_CACHE.mkdir(exist_ok=True)

THEME_MIME = {
    "android": ("application/x-tgtheme-android", ".attheme"),
    "tdesktop": ("application/x-tgtheme-tdesktop", ".tdesktop-theme"),
    "ios": ("application/x-tgtheme-ios", ".tgios-theme"),
}

STICKER_MIME = {".webp": "image/webp", ".png": "image/png", ".webm": "video/webm", ".tgs": "application/x-tgsticker"}


class TGError(RuntimeError):
    pass


class TelegramAccount:
    """Одна сессия на приложение. Клиент создаётся лениво в цикле событий FastAPI."""

    def __init__(self):
        self.client = None
        self._phone_code_hash = None
        self._phone = None

    def _require_lib(self):
        try:
            import telethon  # noqa: F401
        except ImportError as e:
            raise TGError("Установи Telethon: pip install telethon") from e

    async def _get_client(self):
        self._require_lib()
        from telethon import TelegramClient
        s = load_settings()["telegram"]
        if not s.get("api_id") or not s.get("api_hash"):
            raise TGError("Укажи api_id и api_hash (https://my.telegram.org → API development tools)")
        if self.client is None:
            self.client = TelegramClient(str(DATA_DIR / "tg_session"), int(s["api_id"]), s["api_hash"],
                                         device_model="TG Studio", app_version="1.0")
        if not self.client.is_connected():
            await self.client.connect()
        return self.client

    async def status(self) -> dict:
        try:
            cli = await self._get_client()
        except TGError as e:
            return {"authorized": False, "error": str(e)}
        if not await cli.is_user_authorized():
            return {"authorized": False}
        me = await cli.get_me()
        return {"authorized": True, "id": me.id, "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
                "username": me.username, "phone": me.phone}

    async def send_code(self, phone: str) -> dict:
        cli = await self._get_client()
        res = await cli.send_code_request(phone)
        self._phone, self._phone_code_hash = phone, res.phone_code_hash
        return {"sent": True}

    async def sign_in(self, code: str | None = None, password: str | None = None) -> dict:
        from telethon.errors import SessionPasswordNeededError
        cli = await self._get_client()
        try:
            if password and not code:
                await cli.sign_in(password=password)
            else:
                await cli.sign_in(self._phone, code, phone_code_hash=self._phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                return {"need_password": True}
            await cli.sign_in(password=password)
        return await self.status()

    async def logout(self):
        cli = await self._get_client()
        await cli.log_out()
        self.client = None

    async def _authorized(self):
        cli = await self._get_client()
        if not await cli.is_user_authorized():
            raise TGError("Сначала войди в аккаунт Telegram во вкладке «Аккаунт»")
        return cli

    # ---------------- темы ----------------
    async def upload_theme_file(self, path: Path, platform: str, title: str, slug: str | None = None) -> dict:
        from telethon import utils
        from telethon.tl.functions.account import CreateThemeRequest, UploadThemeRequest
        cli = await self._authorized()
        mime, ext = THEME_MIME[platform]
        file = await cli.upload_file(str(path))
        doc = await cli(UploadThemeRequest(file=file, file_name=_safe_name(title) + ext, mime_type=mime))
        slug = _slug(slug or title)
        theme = await cli(CreateThemeRequest(slug=slug, title=title[:64], document=utils.get_input_document(doc)))
        return {"slug": theme.slug, "link": f"https://t.me/addtheme/{theme.slug}", "platform": platform}

    async def create_cloud_theme(self, title: str, settings: dict, wallpaper: bytes | None = None,
                                 slug: str | None = None) -> dict:
        """Облачная тема из настроек — открывается на Android, iOS, macOS и Desktop."""
        from telethon.tl.functions.account import CreateThemeRequest, UploadWallPaperRequest
        from telethon.tl.types import (BaseThemeDay, BaseThemeNight, BaseThemeTinted, InputThemeSettings,
                                       InputWallPaper, WallPaperSettings)
        from ..themes.colors import rgb_int
        cli = await self._authorized()
        base = {"night": BaseThemeNight(), "tinted": BaseThemeTinted(), "day": BaseThemeDay()}[settings["base_theme"]]
        wp = wp_settings = None
        if wallpaper:
            tmp = DATA_DIR / "wp_upload.jpg"
            tmp.write_bytes(wallpaper)
            f = await cli.upload_file(str(tmp))
            wp_settings = WallPaperSettings(blur=False, motion=False)
            paper = await cli(UploadWallPaperRequest(file=f, mime_type="image/jpeg", settings=wp_settings))
            wp = InputWallPaper(id=paper.id, access_hash=paper.access_hash)
        its = InputThemeSettings(
            base_theme=base,
            accent_color=rgb_int(settings["accent_color"]),
            outbox_accent_color=rgb_int(settings["outbox_accent_color"]) if settings.get("outbox_accent_color") else None,
            message_colors=[rgb_int(c) for c in settings.get("message_colors", [])[:4]] or None,
            message_colors_animated=False,
            wallpaper=wp, wallpaper_settings=wp_settings,
        )
        slug = _slug(slug or title)
        theme = await cli(CreateThemeRequest(slug=slug, title=title[:64], settings=[its]))
        return {"slug": theme.slug, "link": f"https://t.me/addtheme/{theme.slug}", "platform": "cloud"}

    # ---------------- языки ----------------
    async def get_langpack(self, platform: str, lang_code: str = "en", refresh: bool = False) -> list[dict]:
        cache = LANGPACK_CACHE / f"{platform}_{lang_code}.json"
        if cache.exists() and not refresh:
            return json.loads(cache.read_text("utf-8"))
        from telethon.tl.functions.langpack import GetLangPackRequest
        from telethon.tl.types import LangPackString, LangPackStringPluralized
        cli = await self._authorized()
        diff = await cli(GetLangPackRequest(lang_pack=platform, lang_code=lang_code))
        out = []
        for s in diff.strings:
            if isinstance(s, LangPackString):
                out.append({"key": s.key, "value": s.value})
            elif isinstance(s, LangPackStringPluralized):
                forms = {f: getattr(s, f + "_value") for f in ("zero", "one", "two", "few", "many", "other")
                         if getattr(s, f + "_value", None)}
                out.append({"key": s.key, "plural": forms})
        out.sort(key=lambda x: x["key"])
        cache.write_text(json.dumps(out, ensure_ascii=False), "utf-8")
        return out

    # ---------------- стикеры / эмодзи от имени аккаунта ----------------
    async def create_sticker_set_user(self, title: str, short_name: str, items: list[dict],
                                      emojis: bool = True, text_color: bool = False, progress=None) -> dict:
        """items: [{path, emoji}]. Пак создаётся на аккаунт пользователя (без бота)."""
        from telethon import utils
        from telethon.tl.functions.messages import UploadMediaRequest
        from telethon.tl.functions.stickers import AddStickerToSetRequest, CreateStickerSetRequest
        from telethon.tl.types import (DocumentAttributeFilename, InputMediaUploadedDocument, InputPeerSelf,
                                       InputStickerSetItem, InputStickerSetShortName, InputUserSelf)
        cli = await self._authorized()

        async def to_item(it):
            p = Path(it["path"])
            f = await cli.upload_file(str(p))
            media = await cli(UploadMediaRequest(peer=InputPeerSelf(), media=InputMediaUploadedDocument(
                file=f, mime_type=STICKER_MIME.get(p.suffix.lower(), "image/png"),
                attributes=[DocumentAttributeFilename(p.name)])))
            return InputStickerSetItem(document=utils.get_input_document(media.document), emoji=it.get("emoji") or "✨")

        short_name = _short_name(short_name or title)
        first = items[:50]
        prepared = []
        for i, it in enumerate(first):
            prepared.append(await to_item(it))
            if progress:
                progress(i + 1, len(items))
        await cli(CreateStickerSetRequest(user_id=InputUserSelf(), title=title[:64], short_name=short_name,
                                          stickers=prepared, emojis=emojis or None,
                                          text_color=text_color or None, software="TG Studio"))
        for j, it in enumerate(items[50:], start=50):
            await cli(AddStickerToSetRequest(stickerset=InputStickerSetShortName(short_name), sticker=await to_item(it)))
            if progress:
                progress(j + 1, len(items))
        kind = "addemoji" if emojis else "addstickers"
        return {"short_name": short_name, "link": f"https://t.me/{kind}/{short_name}"}


# ---------------- Bot API (свой бот от @BotFather) ----------------
class BotStickers:
    def __init__(self, token: str | None = None, user_id: int | str | None = None):
        s = load_settings()["telegram"]
        self.token = token or s.get("bot_token")
        self.user_id = int(user_id or s.get("user_id") or 0)
        if not self.token or not self.user_id:
            raise TGError("Для загрузки через бота нужны bot_token (от @BotFather) и твой user_id "
                          "(узнать у @userinfobot). Не забудь нажать /start у своего бота.")
        self.base = f"https://api.telegram.org/bot{self.token}/"

    async def _call(self, cli, method, data=None, files=None):
        r = await cli.post(self.base + method, data=data, files=files, timeout=120)
        js = r.json()
        if not js.get("ok"):
            raise TGError(f"{method}: {js.get('description')}")
        return js["result"]

    async def create_set(self, title: str, name: str, items: list[dict], sticker_type: str = "custom_emoji",
                         needs_repainting: bool = False, progress=None) -> dict:
        async with httpx.AsyncClient() as cli:
            me = await self._call(cli, "getMe")
            name = _short_name(name or title)
            suffix = f"_by_{me['username']}"
            if not name.lower().endswith(suffix.lower()):
                name = name[:64 - len(suffix)] + suffix

            def sticker_obj(i, it):
                p = Path(it["path"])
                fmt = {".webm": "video", ".tgs": "animated"}.get(p.suffix.lower(), "static")
                return {"sticker": f"attach://f{i}", "format": fmt, "emoji_list": [it.get("emoji") or "✨"]}

            first = items[:50]
            files = {f"f{i}": (Path(it["path"]).name, Path(it["path"]).read_bytes(),
                               mimetypes.guess_type(it["path"])[0] or "application/octet-stream")
                     for i, it in enumerate(first)}
            data = {"user_id": self.user_id, "name": name, "title": title[:64], "sticker_type": sticker_type,
                    "stickers": json.dumps([sticker_obj(i, it) for i, it in enumerate(first)], ensure_ascii=False)}
            if sticker_type == "custom_emoji" and needs_repainting:
                data["needs_repainting"] = "true"
            await self._call(cli, "createNewStickerSet", data, files)
            if progress:
                progress(len(first), len(items))
            for j, it in enumerate(items[50:], start=50):
                p = Path(it["path"])
                await self._call(cli, "addStickerToSet",
                                 {"user_id": self.user_id, "name": name,
                                  "sticker": json.dumps(sticker_obj(0, it), ensure_ascii=False)},
                                 {"f0": (p.name, p.read_bytes(), mimetypes.guess_type(str(p))[0] or "application/octet-stream")})
                if progress:
                    progress(j + 1, len(items))
        kind = "addemoji" if sticker_type == "custom_emoji" else "addstickers"
        return {"short_name": name, "link": f"https://t.me/{kind}/{name}"}


def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\- ]+", "", s, flags=re.U).strip()[:40] or "theme"


def _slug(s: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "", _translit(s))[:20] or "tgstudio"
    return f"{base}{secrets.token_hex(3)}"


def _short_name(s: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", _translit(s)).strip("_")
    base = re.sub(r"_+", "_", base)
    if not base or not base[0].isalpha():
        base = "pack_" + base
    return base[:48]


_TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
               ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def _translit(s: str) -> str:
    out = []
    for c in s:
        t = _TR.get(c.lower())
        out.append(c if t is None else (t.capitalize() if c.isupper() else t))
    return "".join(out)


ACCOUNT = TelegramAccount()
