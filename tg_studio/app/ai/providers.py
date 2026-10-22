"""Подключение нейросетей: с API и без API.

Текстовые провайдеры:
  pollinations   — бесплатно и без ключа (text.pollinations.ai, OpenAI-совместимый)
  claude_cli     — Claude Code CLI (`claude -p`), работает по подписке Claude Pro/Max,
                   без покупки API-кредитов
  ollama         — локальные модели на своём ПК (бесплатно, офлайн)
  gemini         — Google AI Studio (бесплатный ключ с лимитами)
  openai_compat  — любой OpenAI-совместимый сервер: OpenRouter (:free модели), Groq,
                   LM Studio, DeepSeek, Mistral и т.д.
  anthropic      — официальный Claude API (нужны кредиты)
  none           — без ИИ, только алгоритмы

Картинки: pollinations (бесплатно) или локальный Stable Diffusion (AUTOMATIC1111 / Forge).
"""
from __future__ import annotations

import asyncio
import base64
import json
import random
import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

import httpx

from ..config import load_settings
from ..rules import with_rules

PROVIDER_INFO = {
    "pollinations": {"label": "Pollinations — бесплатно, без ключа", "vision": True},
    "claude_cli": {"label": "Claude Code CLI — по подписке Pro/Max, без API-кредитов", "vision": True},
    "ollama": {"label": "Ollama — локально на ПК, бесплатно", "vision": True},
    "gemini": {"label": "Google Gemini — бесплатный ключ AI Studio", "vision": True},
    "openai_compat": {"label": "OpenAI-совместимый (OpenRouter / Groq / LM Studio / DeepSeek)", "vision": True},
    "anthropic": {"label": "Claude API (платно, кредиты)", "vision": True},
    "none": {"label": "Без ИИ — только алгоритмы", "vision": False},
}


class AIError(RuntimeError):
    pass


def http_client(settings: dict | None, timeout: float, **kw) -> httpx.AsyncClient:
    """HTTP-клиент для нейросетей. Если в настройках указан прокси (например, VPN-клиент
    http://127.0.0.1:10809 или socks5://127.0.0.1:1080) — запросы идут через него."""
    proxy = ((settings or load_settings()).get("ai") or {}).get("proxy") or None
    t = httpx.Timeout(timeout, connect=20)
    if not proxy:
        return httpx.AsyncClient(timeout=t, **kw)
    # локальные сервисы (Ollama, LM Studio, Stable Diffusion) — мимо прокси
    mounts = {"all://": httpx.AsyncHTTPTransport(proxy=proxy), "all://127.0.0.1": None, "all://localhost": None}
    return httpx.AsyncClient(timeout=t, mounts=mounts, trust_env=False, **kw)


def friendly_error(e: Exception, provider: str, proxy: str = "") -> str:
    """Понятный текст ошибки сети вместо «Ошибка 500»."""
    name = PROVIDER_INFO.get(provider, {}).get("label", provider).split(" —")[0]
    if proxy and provider != "ollama" and isinstance(e, (httpx.ProxyError, httpx.ConnectError)):
        return (f"Не удалось подключиться через прокси {proxy}. Проверь, что VPN-клиент запущен и порт верный, "
                "или очисти поле «Прокси».")
    if isinstance(e, httpx.TimeoutException):
        return (f"{name} не ответил вовремя. Бесплатные сервисы иногда перегружены — попробуй ещё раз "
                "через минуту или выбери другую нейросеть.")
    if isinstance(e, httpx.ProxyError):
        return f"Не удалось подключиться через прокси ({e}). Проверь адрес прокси в настройках и что VPN запущен."
    if isinstance(e, (httpx.ConnectError, httpx.NetworkError)) and provider == "ollama":
        return ("Ollama не запущена. Установи её с ollama.com, запусти и скачай модель командой "
                "`ollama pull llama3.1` (адрес по умолчанию http://127.0.0.1:11434).")
    if isinstance(e, (httpx.ConnectError, httpx.NetworkError)):
        return (f"Нет соединения с {name}. Проверь интернет. Если сайт заблокирован в твоей стране — "
                "включи VPN или укажи прокси в настройках (поле «Прокси»), либо выбери Ollama (работает офлайн).")
    if isinstance(e, ImportError) and "socks" in str(e).lower():
        return "Для SOCKS-прокси установи пакет: pip install httpx[socks]"
    return f"{name}: {type(e).__name__}: {e}"


def http_error_text(r: httpx.Response) -> str:
    body = r.text[:500]
    try:  # большинство API кладут понятный текст в error.message
        js = r.json()
        err = js.get("error") if isinstance(js, dict) else None
        msg = err.get("message") if isinstance(err, dict) else (err if isinstance(err, str) else None)
        if msg:
            body = str(msg)[:300]
    except ValueError:
        pass
    low = body.lower()
    if "api key not valid" in low or "invalid api key" in low or "incorrect api key" in low:
        return f"{r.status_code}: неверный API-ключ — проверь, что скопировал его полностью."
    if "location is not supported" in low or "unsupported_country" in low or "not available in your" in low:
        return "сервис недоступен в твоей стране — включи VPN или укажи прокси в настройках."
    if r.status_code in (401, 403):
        return f"{r.status_code}: неверный или отсутствующий API-ключ (или доступ запрещён). {body[:200]}"
    if r.status_code in (402, 429):
        return f"{r.status_code}: лимит бесплатных запросов исчерпан — подожди минуту или выбери другую нейросеть."
    if r.status_code == 404:
        return f"404: не найдена модель или адрес — проверь поле «Модель»/«Base URL». {body[:200]}"
    return f"{r.status_code}: {body}"


def extract_json(text: str):
    """Достаёт первый JSON-объект/массив из ответа модели (с ```json и без)."""
    if text is None:
        raise AIError("Пустой ответ модели")
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start is None:
        raise AIError("В ответе нет JSON")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    # обрезанный ответ — пробуем как есть
    return json.loads(text[start:])


def _b64(img: bytes) -> str:
    return base64.b64encode(img).decode()


class AIClient:
    def __init__(self, settings: dict | None = None, section: str | None = None):
        """section — раздел программы: к системному промпту добавляются правила пользователя этого раздела."""
        self.settings = settings or load_settings()
        self.section = section
        ai = self.settings["ai"]
        self.provider = ai.get("provider", "pollinations")
        self.cfg = ai["providers"].get(self.provider, {})
        self.vision = bool(ai.get("vision")) and PROVIDER_INFO.get(self.provider, {}).get("vision", False)

    @property
    def enabled(self) -> bool:
        return self.provider != "none"

    async def chat(self, prompt: str, system: str | None = None, json_mode: bool = False,
                   images: list[bytes] | None = None, max_tokens: int = 4096) -> str:
        if not self.enabled:
            raise AIError("ИИ отключён в настройках (режим «без ИИ»)")
        images = images if (images and self.vision) else None
        system = with_rules(system, self.section)
        if json_mode:
            prompt += "\n\nОтветь ТОЛЬКО валидным JSON без пояснений."
        fn = getattr(self, f"_chat_{self.provider}", None)
        if fn is None:
            raise AIError(f"Неизвестный провайдер: {self.provider}")
        try:
            return await fn(prompt, system, json_mode, images, max_tokens)
        except AIError:
            raise
        except Exception as e:  # noqa: BLE001 — превращаем любую сетевую/системную ошибку в понятную
            raise AIError(friendly_error(e, self.provider, self.settings["ai"].get("proxy") or "")) from e

    def _http(self, timeout: float, **kw) -> httpx.AsyncClient:
        return http_client(self.settings, timeout, **kw)

    async def chat_json(self, prompt: str, system: str | None = None,
                        images: list[bytes] | None = None, max_tokens: int = 4096, retries: int = 2):
        last = None
        for _ in range(retries + 1):
            try:
                text = await self.chat(prompt, system, True, images, max_tokens)
                return extract_json(text)
            except (json.JSONDecodeError, AIError) as e:
                last = e
        raise AIError(f"Модель не вернула корректный JSON: {last}")

    # ---------- OpenAI-совместимые (pollinations, openrouter, groq, lm studio) ----------
    async def _openai_like(self, base_url, api_key, model, prompt, system, json_mode, images, max_tokens,
                           extra: dict | None = None):
        content: list | str = prompt
        if images:
            content = [{"type": "text", "text": prompt}] + [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(im)}"}}
                for im in images
            ]
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        # многие бесплатные модели «думают» перед ответом и тратят на это часть лимита
        body = {"model": model, "messages": messages, "max_tokens": max(max_tokens, 8000)}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        body.update(extra or {})
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        endpoint = base_url.rstrip("/")
        if not endpoint.endswith(("/openai", "/chat/completions")):
            endpoint += "/chat/completions"
        async with self._http(300) as cli:
            r = await cli.post(endpoint, json=body, headers=headers)
            for _ in range(3):  # бесплатные лимиты («1 ответ в 30 секунд») — ждём и повторяем
                if r.status_code not in (402, 429):
                    break
                wait = int(r.headers.get("retry-after") or 31)
                await asyncio.sleep(min(max(wait, 5), 65))
                r = await cli.post(endpoint, json=body, headers=headers)
            if r.status_code == 400 and json_mode:
                body.pop("response_format", None)
                r = await cli.post(endpoint, json=body, headers=headers)
            if r.status_code >= 400:
                raise AIError(http_error_text(r))
            data = r.json()
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as e:
            raise AIError(f"Неожиданный ответ: {str(data)[:300]}") from e
        content = (choice.get("message") or {}).get("content")
        if not content:
            if choice.get("finish_reason") == "length":
                raise AIError("модель потратила весь лимит на размышления и не успела ответить — "
                              "попробуй ещё раз или выбери другую модель")
            raise AIError("модель вернула пустой ответ, попробуй ещё раз")
        return content

    async def _chat_pollinations(self, prompt, system, json_mode, images, max_tokens):
        c = self.cfg
        return await self._openai_like(c.get("base_url") or "https://text.pollinations.ai/openai",
                                       c.get("api_key"), c.get("model") or "openai",
                                       prompt, system, json_mode, images, max_tokens,
                                       # Pollinations кэширует одинаковые запросы — случайный seed даёт новый ответ;
                                       # reasoning_effort=low — модель меньше «думает» и быстрее отвечает
                                       {"seed": random.randint(1, 2**31 - 1), "reasoning_effort": "low"})

    async def _chat_openai_compat(self, prompt, system, json_mode, images, max_tokens):
        c = self.cfg
        if not c.get("base_url"):
            raise AIError("Укажи base_url для OpenAI-совместимого провайдера")
        return await self._openai_like(c["base_url"], c.get("api_key"), c.get("model"),
                                       prompt, system, json_mode, images, max_tokens)

    # ---------- Ollama ----------
    async def _chat_ollama(self, prompt, system, json_mode, images, max_tokens):
        c = self.cfg
        msg = {"role": "user", "content": prompt}
        if images:
            msg["images"] = [_b64(im) for im in images]
        messages = ([{"role": "system", "content": system}] if system else []) + [msg]
        body = {"model": c.get("model") or "llama3.1", "messages": messages, "stream": False,
                "options": {"num_predict": max_tokens}}
        if json_mode:
            body["format"] = "json"
        async with self._http(600) as cli:
            r = await cli.post(c.get("base_url", "http://127.0.0.1:11434").rstrip("/") + "/api/chat", json=body)
            if r.status_code >= 400:
                raise AIError(f"Ollama {r.status_code}: {r.text[:300]}")
            return r.json()["message"]["content"]

    # ---------- Gemini ----------
    async def _chat_gemini(self, prompt, system, json_mode, images, max_tokens):
        c = self.cfg
        if not c.get("api_key"):
            raise AIError("Нужен бесплатный ключ Gemini: https://aistudio.google.com/apikey")
        parts = [{"text": prompt}] + [
            {"inline_data": {"mime_type": "image/png", "data": _b64(im)}} for im in (images or [])
        ]
        body = {"contents": [{"role": "user", "parts": parts}],
                "generationConfig": {"maxOutputTokens": max(max_tokens, 8192)}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        model = c.get("model") or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with self._http(180) as cli:
            r = await cli.post(url, params={"key": c["api_key"]}, json=body)
            if r.status_code >= 400:
                raise AIError("Gemini: " + http_error_text(r))
            data = r.json()
        try:
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise AIError(f"Gemini: пустой ответ {str(data)[:300]}") from e

    # ---------- Claude API (официальный SDK) ----------
    async def _chat_anthropic(self, prompt, system, json_mode, images, max_tokens):
        try:
            import anthropic
        except ImportError as e:
            raise AIError("Установи пакет: pip install anthropic") from e
        c = self.cfg
        client = anthropic.AsyncAnthropic(api_key=c.get("api_key") or None)
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _b64(im)}}
            for im in (images or [])
        ] + [{"type": "text", "text": prompt}]
        kwargs = dict(model=c.get("model") or "claude-opus-5-5", max_tokens=max(max_tokens, 4096),
                      messages=[{"role": "user", "content": content}],
                      output_config={"effort": "low"})
        if system:
            kwargs["system"] = system
        try:
            # серверный фолбэк на другую модель, если основная откажет
            resp = await client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        except TypeError:  # старая версия SDK без параметра fallbacks
            resp = await client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise AIError("Неверный API-ключ Claude") from e
        except anthropic.RateLimitError as e:
            raise AIError("Лимит запросов Claude API, попробуй позже") from e
        except anthropic.APIStatusError as e:
            raise AIError(f"Claude API {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise AIError("Нет соединения с Claude API") from e
        if resp.stop_reason == "refusal":
            raise AIError("Claude отказался выполнять этот запрос")
        return "".join(b.text for b in resp.content if b.type == "text")

    # ---------- Claude Code CLI (подписка, без API) ----------
    async def _chat_claude_cli(self, prompt, system, json_mode, images, max_tokens):
        c = self.cfg
        exe = shutil.which(c.get("command") or "claude")
        if not exe:
            raise AIError("Не найден Claude Code CLI. Установи Node.js (nodejs.org), затем в терминале: "
                          "npm install -g @anthropic-ai/claude-code — и один раз выполни `claude`, "
                          "чтобы войти аккаунтом Claude Pro/Max. После установки перезапусти программу.")
        tmpdir = None
        # в аргументах только простые флаги — длинный текст (системный промпт, правила) идёт через stdin,
        # иначе на Windows cmd.exe ломает строки со спецсимволами
        args = [exe, "-p", "--output-format", "json"]
        if c.get("model"):
            args += ["--model", c["model"]]
        if images:
            tmpdir = Path(tempfile.mkdtemp(prefix="tgs_img_"))
            paths = []
            for i, im in enumerate(images):
                p = tmpdir / f"img{i}.png"
                p.write_bytes(im)
                paths.append(str(p))
            prompt = "Посмотри изображения (прочитай файлы): " + ", ".join(paths) + "\n\n" + prompt
            args += ["--allowedTools", "Read", "--add-dir", str(tmpdir)]
        full = f"ИНСТРУКЦИИ:\n{system}\n\nЗАДАЧА:\n{prompt}" if system else prompt
        env = dict(os.environ)
        proxy = self.settings["ai"].get("proxy")
        if proxy:
            env.update(HTTPS_PROXY=proxy, HTTP_PROXY=proxy)

        def run():
            return subprocess.run(args, input=full.encode("utf-8"), capture_output=True, timeout=900, env=env)
        try:
            proc = await asyncio.to_thread(run)
        except subprocess.TimeoutExpired as e:
            raise AIError("Claude CLI не ответил за 15 минут") from e
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)
        text = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        if proc.returncode != 0 and not text.strip():
            hint = ""
            if any(w in err.lower() for w in ("login", "auth", "api key")):
                hint = " — открой терминал, выполни `claude` и войди аккаунтом Claude Pro/Max."
            raise AIError(f"Claude CLI: {err.strip()[:400] or 'код ' + str(proc.returncode)}{hint}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
        if data.get("is_error"):
            raise AIError(f"Claude CLI: {data.get('result')}")
        return data.get("result", "")


# ---------------- генерация картинок ----------------
async def generate_image(prompt: str, width: int = 512, height: int = 512, seed: int | None = None,
                         negative: str = "", settings: dict | None = None) -> bytes:
    s = (settings or load_settings())["image_ai"]
    provider = s.get("provider", "pollinations")
    if provider == "none":
        raise AIError("Генерация картинок отключена в настройках")
    if provider == "a1111":
        body = {"prompt": prompt, "negative_prompt": negative, "width": width, "height": height,
                "steps": 24, "seed": seed if seed is not None else -1}
        async with http_client(settings, 600) as cli:
            r = await cli.post(s.get("a1111_url", "http://127.0.0.1:7860").rstrip("/") + "/sdapi/v1/txt2img", json=body)
            if r.status_code >= 400:
                raise AIError(f"Stable Diffusion {r.status_code}: {r.text[:300]}")
            return base64.b64decode(r.json()["images"][0])
    params = {"width": width, "height": height, "nologo": "true", "model": s.get("pollinations_model", "flux")}
    if seed is not None:
        params["seed"] = seed
    url = "https://image.pollinations.ai/prompt/" + quote(prompt)
    async with http_client(settings, 240, follow_redirects=True) as cli:
        r = await cli.get(url, params=params)
        if r.status_code >= 400 or not r.headers.get("content-type", "").startswith("image"):
            raise AIError(f"Pollinations {r.status_code}: {r.text[:200]}")
        return r.content


async def diagnose(settings: dict | None = None) -> list[dict]:
    """Проверка доступности всех способов подключения — показывается в настройках."""
    settings = settings or load_settings()
    ai = settings["ai"]
    checks = [
        ("pollinations", "Pollinations", ai["providers"]["pollinations"].get("base_url") or "https://text.pollinations.ai/openai"),
        ("gemini", "Google Gemini", "https://generativelanguage.googleapis.com/"),
        ("openai_compat", "OpenRouter / Groq / свой сервер", ai["providers"]["openai_compat"].get("base_url") or ""),
        ("anthropic", "Claude API", "https://api.anthropic.com/"),
        ("ollama", "Ollama (локально)", (ai["providers"]["ollama"].get("base_url") or "http://127.0.0.1:11434") + "/api/tags"),
    ]
    out = []

    async def probe(key, name, url):
        if not url:
            return {"key": key, "name": name, "ok": False, "detail": "адрес не указан"}
        try:
            async with http_client(settings, 12) as cli:
                r = await cli.get(url)
            if key == "gemini" and "location" in r.text.lower():
                return {"key": key, "name": name, "ok": False, "detail": "недоступен в твоей стране — нужен VPN/прокси"}
            return {"key": key, "name": name, "ok": True, "detail": f"сайт отвечает (HTTP {r.status_code})"}
        except Exception as e:  # noqa: BLE001
            return {"key": key, "name": name, "ok": False, "detail": friendly_error(e, key, ai.get("proxy") or "")}

    out = list(await asyncio.gather(*(probe(*c) for c in checks)))
    exe = shutil.which(ai["providers"]["claude_cli"].get("command") or "claude")
    if exe:
        try:
            r = await asyncio.to_thread(subprocess.run, [exe, "--version"], capture_output=True, timeout=30)
            out.append({"key": "claude_cli", "name": "Claude Code CLI", "ok": r.returncode == 0,
                        "detail": (r.stdout or r.stderr).decode("utf-8", "replace").strip()[:120] + f" ({exe})"})
        except Exception as e:  # noqa: BLE001
            out.append({"key": "claude_cli", "name": "Claude Code CLI", "ok": False, "detail": str(e)})
    else:
        out.append({"key": "claude_cli", "name": "Claude Code CLI", "ok": False,
                    "detail": "не установлен (npm install -g @anthropic-ai/claude-code)"})
    return out


async def test_connection(settings: dict | None = None) -> str:
    client = AIClient(settings)
    return await client.chat("Ответь одним словом: работает?", max_tokens=50)
