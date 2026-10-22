"""Автоматизация translations.telegram.org через Playwright.

У платформы переводов нет публичного API, поэтому программа управляет настоящим
браузером с сохранённым профилем (data/browser_profile):
  1. открывает сайт; если ты не вошёл — ждёт, пока подтвердишь вход в приложении Telegram
     (один раз, дальше сессия сохраняется);
  2. создаёт язык (название, код, базовый язык);
  3. для каждой платформы пытается импортировать файл перевода, а если кнопки импорта нет —
     вносит строки по одной через поиск по ключу.
Если вёрстка сайта изменится и какой-то шаг не найдётся, задача встанет на паузу:
сделай этот шаг руками в открытом окне и нажми «Продолжить» в программе.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from ..config import DATA_DIR, OUTPUT_DIR

SITE = "https://translations.telegram.org"
PROFILE = DATA_DIR / "browser_profile"


async def _first_visible(page, selectors: list[str], timeout: float = 3000):
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:  # noqa: BLE001 — пробуем следующий селектор
            continue
    return None


async def _shot(page, name: str):
    try:
        p = OUTPUT_DIR / "debug"
        p.mkdir(exist_ok=True)
        await page.screenshot(path=str(p / f"{name}.png"))
    except Exception:  # noqa: BLE001
        pass


async def _logged_in(page) -> bool:
    return await page.locator("a[href*='logout'], .header-auth-name, a[href*='/auth/logout']").count() > 0


async def ensure_login(job, page):
    await page.goto(SITE, wait_until="domcontentloaded")
    if await _logged_in(page):
        job.update(message="Уже вошли на translations.telegram.org ✓")
        return
    login = await _first_visible(page, ["a:has-text('Log in')", "a:has-text('Войти')", "a[href*='login']"], 4000)
    if login:
        await login.click()
    job.update(message="Войди в открытом окне: введи номер и подтверди вход в приложении Telegram")
    for _ in range(300):  # до 10 минут
        await asyncio.sleep(2)
        try:
            if await _logged_in(page):
                job.update(message="Вход выполнен ✓ (сессия сохранена)")
                return
        except Exception:  # noqa: BLE001 — страница могла перезагрузиться
            pass
    raise RuntimeError("Не дождались входа на translations.telegram.org")


async def create_language(job, page, name: str, native: str, code: str, base: str):
    await page.goto(f"{SITE}/{code}/", wait_until="domcontentloaded")
    if page.url.rstrip("/").endswith(f"/{code}") and await page.locator(f"a[href^='/{code}/']").count() > 3:
        job.update(message=f"Язык «{code}» уже существует — обновляю строки")
        return
    await page.goto(SITE + "/languages", wait_until="domcontentloaded")
    btn = await _first_visible(page, [
        "a:has-text('Add a new language')", "button:has-text('Add a new language')",
        "a:has-text('Create language')", "button:has-text('Create')", "a:has-text('New language')",
        "a:has-text('Добавить')",
    ])
    if not btn:
        await _shot(page, "no_create_button")
        await job.wait_user(f"Нажми «Add a new language» и создай язык: название «{name}», "
                            f"короткое имя (код) «{code}», базовый язык «{base}». Затем «Продолжить».")
        return
    await btn.click()
    await asyncio.sleep(1)
    filled = 0
    for value, hints in ((name, ["name", "title"]), (native, ["native"]), (code, ["short", "code", "lang_code"])):
        for h in hints:
            loc = page.locator(f"input[name*='{h}' i], input[placeholder*='{h}' i]").first
            if await loc.count():
                await loc.fill(value)
                filled += 1
                break
    sel = page.locator("select").first
    if await sel.count():
        try:
            await sel.select_option(value=base)
        except Exception:  # noqa: BLE001
            pass
    if filled < 2:
        await _shot(page, "create_form")
        await job.wait_user(f"Заполни форму: «{name}», код «{code}», базовый язык «{base}», сохрани и нажми «Продолжить».")
        return
    submit = await _first_visible(page, ["button[type=submit]", "button:has-text('Save')", "button:has-text('Create')"])
    if submit:
        await submit.click()
        await asyncio.sleep(2)
    job.update(message=f"Язык «{name}» ({code}) создан")


async def try_import(job, page, code: str, platform: str, file_path: str) -> bool:
    await page.goto(f"{SITE}/{code}/{platform}/", wait_until="domcontentloaded")
    imp = await _first_visible(page, ["a:has-text('Import')", "button:has-text('Import')", "a:has-text('Импорт')"], 2500)
    if imp:
        await imp.click()
        await asyncio.sleep(1)
    file_input = page.locator("input[type=file]").first
    if not await file_input.count():
        return False
    await file_input.set_input_files(file_path)
    await asyncio.sleep(1)
    submit = await _first_visible(page, ["button:has-text('Import')", "button:has-text('Upload')",
                                         "button[type=submit]", "button:has-text('Save')"], 4000)
    if submit:
        await submit.click()
    await asyncio.sleep(3)
    job.update(message=f"{platform}: файл импортирован")
    return True


async def push_strings(job, page, code: str, platform: str, entries: list[dict], start_p: float, span: float):
    """Построчная загрузка (медленно, но работает без кнопки импорта)."""
    flat = []
    for e in entries:
        if "plural" in e:
            flat.extend((e["key"], f, v) for f, v in e["plural"].items())
        else:
            flat.append((e["key"], None, e["value"]))
    ok = 0
    for i, (key, form, value) in enumerate(flat):
        try:
            await page.goto(f"{SITE}/{code}/{platform}/?query={key}", wait_until="domcontentloaded")
            item = page.locator(f"a[href*='/{key}'], .tr-key-row:has-text('{key}')").first
            if await item.count():
                await item.click()
                await asyncio.sleep(0.4)
            add = await _first_visible(page, ["a:has-text('Add Translation')", "button:has-text('Add Translation')",
                                              "a:has-text('Edit')"], 1500)
            if add:
                await add.click()
            areas = page.locator("textarea:visible, div[contenteditable=true]:visible")
            n = await areas.count()
            if n == 0:
                continue
            idx = 0
            if form and n > 1:
                idx = ["zero", "one", "two", "few", "many", "other"].index(form) % n
            area = areas.nth(idx)
            await area.fill(value)
            submit = await _first_visible(page, ["button:has-text('Submit')", "button:has-text('Save')",
                                                 "button[type=submit]"], 1500)
            if submit:
                await submit.click()
                ok += 1
            await asyncio.sleep(0.3)
        except Exception as e:  # noqa: BLE001
            job.update(message=f"{key}: {e}")
        if i % 10 == 0:
            job.update(start_p + span * (i + 1) / len(flat), f"{platform}: {i + 1}/{len(flat)} (успешно {ok})")
    return ok


async def upload_language(job, name: str, native: str, code: str, base: str,
                          files: dict[str, str], entries: dict[str, list[dict]], headless: bool = False,
                          allow_per_key: bool = True) -> dict:
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RuntimeError("Установи Playwright: pip install playwright && playwright install chromium") from e
    code = re.sub(r"[^a-z0-9\-]", "", code.lower())[:32]
    PROFILE.mkdir(parents=True, exist_ok=True)
    report = {"code": code, "link": f"https://t.me/setlanguage/{code}", "platforms": {}}
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(str(PROFILE), headless=headless,
                                                         viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            job.update(0.02, "Открываю translations.telegram.org")
            await ensure_login(job, page)
            await create_language(job, page, name, native, code, base)
            plats = list(files)
            for n, platform in enumerate(plats):
                start, span = 0.1 + 0.9 * n / len(plats), 0.9 / len(plats)
                job.update(start, f"{platform}: загрузка строк")
                if await try_import(job, page, code, platform, files[platform]):
                    report["platforms"][platform] = "import"
                    continue
                if not allow_per_key:
                    await job.wait_user(f"Импортируй файл {Path(files[platform]).name} для {platform} вручную "
                                        "в открытом окне и нажми «Продолжить».")
                    report["platforms"][platform] = "manual"
                    continue
                ok = await push_strings(job, page, code, platform, entries[platform], start, span)
                report["platforms"][platform] = f"по одной: {ok}"
        finally:
            await _shot(page, "last_state")
            await ctx.close()
    return report
