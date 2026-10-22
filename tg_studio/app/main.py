"""TG Studio — веб-интерфейс и API (FastAPI). Запуск: python run.py"""
from __future__ import annotations

import base64
import io
import json
import re
import shutil
import time
import uuid
from pathlib import Path

import numpy as np
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import config, rules
from .ai.providers import PROVIDER_INFO, AIClient, AIError, generate_image, test_connection
from .config import LUT_DIR, OUTPUT_DIR, STATIC_DIR, UPLOAD_DIR
from .emoji import composer, pixelgen
from .emoji.convert import frames_to_gif
from .imageutil import draw_text_block, fit, list_fonts
from .jobs import JOBS, start_job
from .lang import builder as lang_b
from .stickers import processor as st
from .text import ai_text
from .text.charmaps import charmap_table, parse_custom_map
from .tg.client import ACCOUNT, BotStickers, TGError
from .themes import exporters as th_exp
from .themes import generator as th_gen
from .themes.palette import extract_palette, wallpaper_brightness

app = FastAPI(title="TG Studio")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.exception_handler(AIError)
async def _ai_err(_, e):
    return JSONResponse({"error": f"ИИ: {e}"}, status_code=400)


@app.exception_handler(TGError)
async def _tg_err(_, e):
    return JSONResponse({"error": str(e)}, status_code=400)


@app.exception_handler(ValueError)
async def _val_err(_, e):
    return JSONResponse({"error": str(e)}, status_code=400)


def url_of(path: str | Path) -> str:
    p = Path(path).resolve()
    for base, prefix in ((OUTPUT_DIR, "/output/"), (UPLOAD_DIR, "/uploads/")):
        try:
            return prefix + p.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return str(p)


def data_url(img: Image.Image, fmt: str = "PNG") -> str:
    b = io.BytesIO()
    img.save(b, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()


def safe_upload(name: str) -> Path:
    p = (UPLOAD_DIR / Path(name).name).resolve()
    if not p.exists():
        raise HTTPException(404, f"Файл не найден: {name}")
    return p


def new_out_dir(prefix: str) -> Path:
    d = OUTPUT_DIR / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# ======================= общее =======================
@app.get("/api/settings")
async def get_settings():
    return {"settings": config.public_settings(), "providers": PROVIDER_INFO}


@app.post("/api/settings")
async def set_settings(patch: dict = Body(...)):
    config.save_settings(config.strip_masked(patch))
    return {"settings": config.public_settings()}


@app.post("/api/ai/test")
async def ai_test():
    t = time.time()
    reply = await test_connection()
    return {"reply": reply[:200], "seconds": round(time.time() - t, 1)}


@app.get("/api/fonts")
async def fonts():
    return {"fonts": list_fonts()}


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    out = []
    for f in files:
        ext = Path(f.filename or "file").suffix.lower() or ".png"
        stem = re.sub(r"[^\w\-]+", "_", Path(f.filename or "img").stem)[:40]
        name = f"{stem}_{uuid.uuid4().hex[:6]}{ext}"
        dest = UPLOAD_DIR / name
        with dest.open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        out.append(_lib_entry(dest))
    return {"files": out}


def _lib_entry(p: Path) -> dict:
    try:
        with Image.open(p) as im:
            w, h, anim = im.width, im.height, bool(getattr(im, "is_animated", False))
    except Exception:  # noqa: BLE001
        w = h = 0
        anim = False
    return {"name": p.name, "url": url_of(p), "w": w, "h": h, "animated": anim}


@app.get("/api/library")
async def library():
    files = sorted(UPLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"files": [_lib_entry(p) for p in files if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif")]}


@app.delete("/api/library/{name}")
async def library_delete(name: str):
    safe_upload(name).unlink()
    return {"ok": True}


@app.get("/api/jobs/{jid}")
async def job_status(jid: str):
    j = JOBS.get(jid)
    if not j:
        raise HTTPException(404, "Нет такой задачи")
    return j.as_dict()


@app.post("/api/jobs/{jid}/continue")
async def job_continue(jid: str):
    j = JOBS.get(jid)
    if j:
        j.resume()
    return {"ok": True}


@app.get("/api/outputs")
async def outputs():
    items = []
    for p in sorted(OUTPUT_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        items.append({"name": p.name, "url": url_of(p), "size": p.stat().st_size, "time": p.stat().st_mtime})
    return {"items": items}


# ======================= Telegram аккаунт =======================
@app.get("/api/tg/status")
async def tg_status():
    return await ACCOUNT.status()


@app.post("/api/tg/send_code")
async def tg_send_code(data: dict = Body(...)):
    phone = data.get("phone") or config.load_settings()["telegram"].get("phone")
    if not phone:
        raise HTTPException(400, "Укажи номер телефона")
    config.save_settings({"telegram": {"phone": phone}})
    return await ACCOUNT.send_code(phone)


@app.post("/api/tg/sign_in")
async def tg_sign_in(data: dict = Body(...)):
    return await ACCOUNT.sign_in(data.get("code"), data.get("password"))


@app.post("/api/tg/logout")
async def tg_logout():
    await ACCOUNT.logout()
    return {"ok": True}


# ======================= темы =======================


@app.post("/api/theme/palette")
async def theme_palette(data: dict = Body(...)):
    p = safe_upload(data["file"])
    with Image.open(p) as im:
        im = im.convert("RGB")
        pal = extract_palette(im, int(data.get("count", 15)), int(data.get("seed", 0)))
        bright = wallpaper_brightness(im)
    return {"palette": pal, "brightness": bright}


@app.get("/api/theme/meta")
async def theme_meta():
    boost = float(rules.section("themes").get("contrast_boost") or 0) / 100
    return {"roles": th_gen.ROLE_KEYS, "labels": th_gen.ROLE_LABELS, "styles": th_gen.STYLES,
            "rules": [(fg, bg, round(min(21.0, r * (1 + boost)), 2)) for fg, bg, r in th_gen.CONTRAST_RULES],
            "locked": rules.theme_locked()}


def _theme_rules() -> tuple[str, float, dict, list]:
    r = rules.section("themes")
    return r.get("mode") or "", float(r.get("contrast_boost") or 0) / 100, rules.theme_locked(), r.get("styles") or []


def _finish_themes(themes: list[dict]) -> list[dict]:
    """Применяет жёсткие правила тем: закреплённые цвета и усиленный контраст."""
    _, boost, locked, _ = _theme_rules()
    out = []
    for t in themes:
        meta = t.get("_meta")
        t = th_gen.fix_contrast(t, boost, locked) if (boost or locked) else t
        if meta:
            t["_meta"] = meta
        out.append({"roles": t, "report": th_gen.contrast_report(t, boost)})
    return out


@app.post("/api/theme/generate")
async def theme_generate(data: dict = Body(...)):
    pal = data["palette"]
    mode_rule, _, _, styles = _theme_rules()
    themes = th_gen.theme_variants(pal, mode_rule or data.get("mode", "auto"), int(data.get("count", 6)),
                                   data.get("brightness"), styles)
    return {"themes": _finish_themes(themes)}


@app.post("/api/theme/ai")
async def theme_ai(data: dict = Body(...)):
    pal = data["palette"]
    ai = AIClient(section="themes")
    count = int(data.get("count", 3))
    mode_rule, _, locked, _ = _theme_rules()
    desc = data.get("description", "")
    if locked:
        desc += " Обязательно используй цвета: " + ", ".join(f"{k}={v}" for k, v in locked.items())
    raw = await ai.chat_json(th_gen.ai_prompt(pal, desc, mode_rule or data.get("mode", "auto"), count),
                             system=th_gen.AI_SYSTEM, max_tokens=12000)
    return {"themes": _finish_themes(th_gen.normalize_ai_themes(raw, pal))}


@app.post("/api/theme/fix")
async def theme_fix(data: dict = Body(...)):
    _, boost, locked, _ = _theme_rules()
    roles = th_gen.fix_contrast(data["roles"], boost, locked) if data.get("fix", True) else data["roles"]
    return {"roles": roles, "report": th_gen.contrast_report(roles, boost)}


def _wallpaper_bytes(data: dict) -> bytes | None:
    if data.get("wallpaper"):
        return safe_upload(data["wallpaper"]).read_bytes()
    return None


@app.post("/api/theme/export")
async def theme_export(data: dict = Body(...)):
    roles, name = data["roles"], data.get("name") or "TG Studio"
    wp = _wallpaper_bytes(data) if data.get("use_wallpaper", True) else None
    d = new_out_dir("theme")
    safe = re.sub(r"[^\w\-]+", "_", name)[:30] or "theme"
    files = {
        "android": d / f"{safe}.attheme",
        "tdesktop": d / f"{safe}.tdesktop-theme",
        "tdesktop_palette": d / f"{safe}.tdesktop-palette",
        "ios": d / f"{safe}.tgios-theme",
        "json": d / f"{safe}.json",
    }
    files["android"].write_bytes(th_exp.to_attheme(roles, wp))
    files["tdesktop"].write_bytes(th_exp.to_tdesktop_theme(roles, wp))
    files["tdesktop_palette"].write_text(th_exp.to_tdesktop_palette(roles), "utf-8")
    files["ios"].write_text(th_exp.to_tgios(roles, name), "utf-8")
    files["json"].write_text(json.dumps({"name": name, "roles": roles}, ensure_ascii=False, indent=1), "utf-8")
    if data.get("palette"):
        (d / "palette.png").write_bytes(th_exp.palette_png(data["palette"]))
        files["palette"] = d / "palette.png"
    zpath = shutil.make_archive(str(d), "zip", d)
    return {"files": {k: url_of(v) for k, v in files.items()}, "zip": url_of(zpath), "dir": str(d)}


@app.post("/api/theme/publish")
async def theme_publish(data: dict = Body(...)):
    """Создаёт темы прямо в аккаунте Telegram: облачную (все платформы) и/или файловые."""
    roles, name = data["roles"], data.get("name") or "TG Studio"
    wp = _wallpaper_bytes(data) if data.get("use_wallpaper", True) else None
    platforms = data.get("platforms") or ["cloud"]
    d = new_out_dir("theme_pub")
    links = []
    for pf in platforms:
        if pf == "cloud":
            jpg = None
            if wp:
                im = Image.open(io.BytesIO(wp)).convert("RGB")
                im.thumbnail((1440, 2560))
                b = io.BytesIO()
                im.save(b, "JPEG", quality=90)
                jpg = b.getvalue()
            links.append(await ACCOUNT.create_cloud_theme(name, th_exp.cloud_theme_settings(roles), jpg))
        elif pf == "android":
            p = d / "theme.attheme"
            p.write_bytes(th_exp.to_attheme(roles, wp))
            links.append(await ACCOUNT.upload_theme_file(p, "android", name))
        elif pf == "tdesktop":
            p = d / "theme.tdesktop-theme"
            p.write_bytes(th_exp.to_tdesktop_theme(roles, wp))
            links.append(await ACCOUNT.upload_theme_file(p, "tdesktop", name))
        elif pf == "ios":
            p = d / "theme.tgios-theme"
            p.write_text(th_exp.to_tgios(roles, name), "utf-8")
            links.append(await ACCOUNT.upload_theme_file(p, "ios", name))
    return {"links": links}


# ======================= языки =======================


@app.get("/api/charmaps")
async def charmaps():
    return {"fonts": charmap_table(), "platforms": lang_b.PLATFORMS}


@app.post("/api/lang/source")
async def lang_source(data: dict = Body(...)):
    entries = await ACCOUNT.get_langpack(data.get("platform", "android"), data.get("lang_code", "ru"),
                                         bool(data.get("refresh")))
    return {"count": len(entries), "sample": entries[:40],
            "preview": lang_b.preview(entries, data.get("platform", "android"))}


def _lang_map(data: dict) -> dict:
    return lang_b.build_mapping(data.get("presets") or [], parse_custom_map(data.get("custom_map") or ""))


@app.post("/api/lang/preview")
async def lang_preview(data: dict = Body(...)):
    platform = data.get("platform", "android")
    try:
        entries = await ACCOUNT.get_langpack(platform, data.get("lang_code", "ru"))
        src = lang_b.preview(entries, platform)
    except TGError:
        src = {}
    if not src:  # без входа в Telegram — демо-строки
        src = {"Chats": "Чаты", "Contacts": "Контакты", "Settings": "Настройки", "Search": "Поиск",
               "TypeMessage": "Сообщение", "Online": "в сети", "SavedMessages": "Избранное",
               "Send": "Отправить", "Reply": "Ответить", "Forward": "Переслать",
               "Delete": "Удалить %1$s сообщений?"}
    if data.get("texts"):
        src = data["texts"]
    mode = data.get("mode", "charmap")
    mapping = _lang_map(data)
    work = rules.lang_pre(src, lang_b.split_protected)
    if mode == "charmap":
        out = {k: lang_b.apply_map(v, mapping) for k, v in work.items()}
    else:
        class _J:  # мини-заглушка задачи для предпросмотра
            def update(self, *a, **k):
                pass
        out = await lang_b.ai_rewrite(_J(), work, data.get("description", ""), data.get("target_lang", "русский"),
                                      AIClient(section="lang"), fallback_map=mapping or None,
                                      examples=data.get("examples", ""))
        if mode == "both" and mapping:
            out = {k: lang_b.apply_map(v, mapping) for k, v in out.items()}
    return {"source": src, "result": rules.lang_post(out, lang_b.split_protected)}


async def _lang_job(job, data: dict):
    platforms = data.get("platforms") or ["android"]
    name = data.get("name") or "My Language"
    code = re.sub(r"[^a-z0-9\-]", "", (data.get("code") or "mylang").lower())[:32] or "mylang"
    mapping = _lang_map(data)
    mode = data.get("mode", "charmap")
    ai = AIClient(section="lang") if mode in ("ai", "both") else None
    per_platform = {}
    for n, pf in enumerate(platforms):
        job.update(n / len(platforms) * 0.5, f"{pf}: загружаю исходные строки ({data.get('lang_code', 'ru')})")
        entries = await ACCOUNT.get_langpack(pf, data.get("lang_code", "ru"))
        chosen = lang_b.select_entries(entries, data.get("key_filter", ""), int(data.get("limit") or 0))
        flat = rules.lang_pre(lang_b.flatten(chosen), lang_b.split_protected)
        if mode == "charmap":
            res = {k: lang_b.apply_map(v, mapping) for k, v in flat.items()}
        else:
            res = await lang_b.ai_rewrite(job, flat, data.get("description", ""), data.get("target_lang", "русский"),
                                          ai, fallback_map=mapping or None, examples=data.get("examples", ""))
            if mode == "both" and mapping:
                res = {k: lang_b.apply_map(v, mapping) for k, v in res.items()}
        # строки вне выборки — замена символов (если задана) или исходник
        full = rules.lang_pre(lang_b.flatten(entries), lang_b.split_protected)
        if data.get("rest_charmap", True) and mapping:
            full = {k: lang_b.apply_map(v, mapping) for k, v in full.items()}
        full.update(res)
        full = rules.lang_post(full, lang_b.split_protected)
        per_platform[pf] = lang_b.unflatten(full, entries) if data.get("full_pack", True) else lang_b.unflatten(res, chosen)
        job.update((n + 1) / len(platforms) * 0.5, f"{pf}: готово {len(res)} строк")
    out_dir = new_out_dir(f"lang_{code}")
    files = lang_b.save_language(out_dir, code, per_platform)
    zpath = shutil.make_archive(str(out_dir), "zip", out_dir)
    result = {"files": {k: url_of(v) for k, v in files.items()}, "zip": url_of(zpath), "dir": str(out_dir),
              "code": code, "preview": {pf: lang_b.preview(e, pf) for pf, e in per_platform.items()}}
    if data.get("upload"):
        from .lang.web_uploader import upload_language
        job.update(0.5, "Загружаю на translations.telegram.org")
        rep = await upload_language(job, name, data.get("native_name") or name, code, data.get("base", "ru"),
                                    files, per_platform, headless=bool(config.load_settings()["translations"].get("headless")))
        result["upload"] = rep
        result["link"] = rep["link"]
    return result


@app.post("/api/lang/build")
async def lang_build(data: dict = Body(...)):
    return {"job": start_job("Создание языка", _lang_job, data).id}


# ======================= эмодзи =======================


@app.post("/api/emoji/analyze")
async def emoji_analyze(data: dict = Body(...)):
    return {"items": [composer.analyze(safe_upload(f)) for f in data["files"]]}


@app.post("/api/emoji/layout")
async def emoji_layout(data: dict = Body(...)):
    files = [Path(f).name for f in data["files"]]
    for f in files:
        safe_upload(f)
    cols, rows = int(data.get("cols", 8)), int(data.get("rows", 25))
    if data.get("mode") == "ai":
        items = await composer.ai_layout(files, data.get("description", ""), AIClient(section="emoji"), cols, rows)
    else:
        items = composer.auto_layout(files, cols, rows, data.get("style", "balanced"))
    for it in items:
        it.pop("analysis", None)
    return {"items": items}


@app.post("/api/emoji/pack")
async def emoji_pack(data: dict = Body(...)):
    return {"items": composer.pack(data["items"], int(data.get("cols", 8)), int(data.get("rows", 25)),
                                   keep_fixed=bool(data.get("keep_fixed", True)))}


@app.post("/api/emoji/render_item")
async def emoji_render_item(data: dict = Body(...)):
    frames, _ = composer.render_item(data["item"], int(data.get("cell", 100)))
    return {"image": data_url(frames[0]), "animated": len(frames) > 1}


@app.post("/api/emoji/preview")
async def emoji_preview(data: dict = Body(...)):
    board = composer.render_board(data["items"], int(data.get("cols", 8)), int(data.get("rows", 25)),
                                  background=data.get("background"))
    img = board["preview"]
    scale = float(data.get("scale", 0.5))
    if scale != 1:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    return {"image": data_url(img), "rows_used": board["rows_used"]}


async def _emoji_job(job, data: dict):
    boards = data["boards"]
    out_root = new_out_dir("emoji")
    results = []
    for bi, b in enumerate(boards):
        name = re.sub(r"[^\w\-]+", "_", b.get("name") or f"pack{bi}")[:30]

        def prog(n, total, bi=bi):
            job.update((bi + n / max(1, total) * 0.7) / len(boards), f"«{b.get('title', name)}»: эмодзи {n}/{total}")
        res = composer.export_board(b["items"], out_root / name, name, int(b.get("cols", 8)), int(b.get("rows", 25)),
                                    b.get("emoji") or "✨", bool(data.get("svg")), bool(data.get("tgs")),
                                    bool(b.get("skip_empty_rows", False)), prog)
        entry = {"title": b.get("title") or name, "zip": url_of(res["zip"]), "canvas": url_of(res["canvas"]),
                 "count": res["count"],
                 "tiles": [{"url": url_of(t.get("gif") or t.get("png") or t["file"]), "emoji": t["emoji"],
                            "row": t["row"], "col": t["col"]} for t in res["tiles"]]}
        upload = data.get("upload", "none")
        if upload != "none":
            items = [{"path": t["file"], "emoji": t["emoji"]} for t in res["tiles"]]
            if len(items) > 200:
                job.update(message="⚠ В эмодзи-паке максимум 200 эмодзи — лишние не загружены")
                items = items[:200]

            def up(n, total, bi=bi):
                job.update((bi + 0.7 + 0.3 * n / max(1, total)) / len(boards), f"Загрузка в Telegram: {n}/{total}")
            title = b.get("title") or name
            short = b.get("short_name") or title
            if upload == "bot":
                link = await BotStickers().create_set(title, short, items, "custom_emoji",
                                                      bool(b.get("needs_repainting")), up)
            else:
                link = await ACCOUNT.create_sticker_set_user(title, short, items, emojis=True,
                                                             text_color=bool(b.get("needs_repainting")), progress=up)
            entry["link"] = link["link"]
        results.append(entry)
    return {"packs": results}


@app.post("/api/emoji/export")
async def emoji_export(data: dict = Body(...)):
    return {"job": start_job("Эмодзи-пак", _emoji_job, data).id}


@app.post("/api/emoji/banner")
async def emoji_banner(data: dict = Body(...)):
    w, h = int(data.get("w", 4)), int(data.get("h", 1))
    if data.get("prompt"):
        raw = await generate_image(data["prompt"] + ", wide aesthetic banner, no text", w * 256, h * 256,
                                   data.get("seed"))
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        if data.get("text"):
            img = fit(img, (w * 100 * 2, h * 100 * 2), "cover")
            img = draw_text_block(img, data["text"], data.get("font"), int(data.get("size", 46)) * 2,
                                  data.get("text_color", "#ffffff"), 4, "#00000088")
    else:
        img = composer.make_text_banner(data.get("text", "♡"), w, h, data.get("colors") or ["#ff9ac1", "#a18cd1"],
                                        data.get("font"), data.get("text_color", "#ffffff"), data.get("deco", ""),
                                        int(data.get("size", 46)))
    name = f"banner_{uuid.uuid4().hex[:6]}.png"
    img.save(UPLOAD_DIR / name)
    return {"file": _lib_entry(UPLOAD_DIR / name), "w": w, "h": h}


@app.post("/api/emoji/aiimage")
async def emoji_aiimage(data: dict = Body(...)):
    """Нейросеть рисует картинку для пака (арт, фон баннера, наклейку)."""
    w, h = int(data.get("width", 512)), int(data.get("height", 512))
    raw = await generate_image(data["prompt"], w, h, data.get("seed"))
    name = f"ai_{uuid.uuid4().hex[:6]}.png"
    Image.open(io.BytesIO(raw)).save(UPLOAD_DIR / name)
    return {"file": _lib_entry(UPLOAD_DIR / name)}


@app.get("/api/pixel/meta")
async def pixel_meta():
    return {"animations": pixelgen.ANIMATIONS, "sprites": list(pixelgen.SPRITES)}


@app.post("/api/pixel/generate")
async def pixel_generate(data: dict = Body(...)):
    src = None
    if data.get("file"):
        src = Image.open(safe_upload(data["file"]))
    res = await pixelgen.generate(data.get("prompt", ""), data.get("mode", "procedural"), int(data.get("size", 24)),
                                  data.get("animation", "sparkle"), int(data.get("frames", 12)), int(data.get("fps", 10)),
                                  int(data.get("colors", 12)), bool(data.get("outline", True)), data.get("sprite", "heart"),
                                  data.get("seed"), AIClient(section="pixel"), src)
    d = OUTPUT_DIR / "pixel"
    stem = f"px_{uuid.uuid4().hex[:8]}"
    files = pixelgen.export(res["frames"], res["fps"], d, stem)
    out = {k: url_of(v) for k, v in files.items()}
    lib_name = f"{stem}.gif"
    big = pixelgen.upscale_frames(res["frames"], 100)
    frames_to_gif(big, int(1000 / res["fps"]), UPLOAD_DIR / lib_name)  # в библиотеку — для композитора
    return {"files": out, "library": lib_name, "seed": res["seed"]}


# ======================= стикеры =======================


@app.get("/api/stickers/meta")
async def stickers_meta():
    return {"luts": st.list_luts(), "frames": st.FRAMES}


@app.post("/api/stickers/lut_upload")
async def lut_upload(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        name = Path(f.filename or "lut.cube").name
        with (LUT_DIR / name).open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        saved.append(name)
    return {"saved": saved, "luts": st.list_luts()}


@app.post("/api/stickers/preview")
async def sticker_preview(data: dict = Body(...)):
    img = Image.open(safe_upload(data["file"]))
    lut = st.load_lut(data.get("opts", {}).get("lut"))
    out = st.process(img, data.get("opts", {}), None, lut)
    out.thumbnail((320, 320))
    return {"image": data_url(out)}


EMOJI_SYSTEM = "Подбираешь эмодзи к стикерам. Отвечаешь только JSON."


async def _sticker_job(job, data: dict):
    files = data["files"]
    opts = data.get("opts", {})
    per = data.get("per_file", {})
    lut = st.load_lut(opts.get("lut"))
    harmony = None
    if opts.get("harmonize", True) and len(files) > 1:
        stats = [st.lab_stats(Image.open(safe_upload(f))) for f in files]
        harmony = (np.mean([s[0] for s in stats], axis=0), np.mean([s[1] for s in stats], axis=0))
    out_dir = new_out_dir("stickers")
    paths, items = [], []
    emojis = data.get("emojis") or {}
    ai = AIClient(section="stickers")
    for i, f in enumerate(files):
        job.update(i / len(files) * 0.7, f"Обработка {i + 1}/{len(files)}")
        img = Image.open(safe_upload(f))
        o = dict(opts)
        o.update(per.get(f, {}))
        res = st.process(img, o, harmony, st.load_lut(o["lut"]) if o.get("lut") != opts.get("lut") else lut)
        p = st.save_sticker(res, out_dir / f"sticker_{i:02d}.webp")
        paths.append(p)
        emo = emojis.get(f)
        if not emo and data.get("ai_emoji") and ai.enabled:
            try:
                r = await ai.chat_json("Подбери одно эмодзи, которое лучше всего описывает этот стикер. "
                                       'Ответ: {"emoji": "😊"}', system=EMOJI_SYSTEM,
                                       images=[st.png_bytes(res, 256)])
                emo = r.get("emoji")
            except Exception:  # noqa: BLE001
                emo = None
        items.append({"path": str(p), "emoji": emo or data.get("default_emoji")
                      or rules.section("stickers").get("default_emoji") or "✨"})
    sheet = st.contact_sheet(paths)
    sheet.save(out_dir / "preview.png")
    zpath = shutil.make_archive(str(out_dir), "zip", out_dir)
    result = {"zip": url_of(zpath), "preview": url_of(out_dir / "preview.png"),
              "stickers": [{"url": url_of(it["path"]), "emoji": it["emoji"]} for it in items]}
    upload = data.get("upload", "none")
    if upload != "none":
        title = data.get("title") or "My stickers"

        def up(n, total):
            job.update(0.7 + 0.3 * n / max(1, total), f"Загрузка в Telegram: {n}/{total}")
        if upload == "bot":
            link = await BotStickers().create_set(title, data.get("short_name") or title, items, "regular", progress=up)
        else:
            link = await ACCOUNT.create_sticker_set_user(title, data.get("short_name") or title, items,
                                                         emojis=False, progress=up)
        result["link"] = link["link"]
    return result


@app.post("/api/stickers/build")
async def sticker_build(data: dict = Body(...)):
    return {"job": start_job("Стикер-пак", _sticker_job, data).id}


# ======================= тексты =======================


@app.post("/api/text/ai")
async def text_ai(data: dict = Body(...)):
    res = await ai_text.run(data.get("action", "post"), data)
    return {"result": res}


# ======================= правила =======================
@app.get("/api/rules")
async def rules_get():
    d = rules.load()
    return {**d, "sections": rules.SECTION_LABELS, "styles": th_gen.STYLES, "roles": th_gen.ROLE_KEYS}


@app.post("/api/rules")
async def rules_set(data: dict = Body(...)):
    return rules.save(rules=data.get("rules"), active=data.get("active"))


@app.post("/api/rules/preset")
async def rules_preset(data: dict = Body(...)):
    """action: save (текущие правила под именем) | load | delete"""
    d = rules.load()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Укажи название набора")
    presets = d["presets"]
    if data.get("action") == "delete":
        presets.pop(name, None)
        return rules.save(presets=presets, active="" if d["active"] == name else d["active"])
    if data.get("action") == "load":
        if name not in presets:
            raise HTTPException(404, "Нет такого набора")
        return rules.save(rules=presets[name], active=name)
    presets[name] = d["rules"]
    return rules.save(presets=presets, active=name)


@app.post("/api/rules/apply_text")
async def rules_apply_text(data: dict = Body(...)):
    return {"text": rules.apply_text(data.get("text", ""), bool(data.get("full_post", True)))}
