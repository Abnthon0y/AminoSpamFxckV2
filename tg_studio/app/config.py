"""Пути проекта и хранение настроек (data/settings.json)."""
from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
LUT_DIR = BASE_DIR / "luts"
FONTS_DIR = BASE_DIR / "fonts"
SETTINGS_FILE = DATA_DIR / "settings.json"

for _d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, LUT_DIR, FONTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DEFAULTS: dict = {
    "ai": {
        # pollinations | claude_cli | ollama | gemini | openai_compat | anthropic | none
        "provider": "pollinations",
        "vision": False,
        "proxy": "",  # http://127.0.0.1:10809 или socks5://127.0.0.1:1080 — если сервисы заблокированы
        "providers": {
            "pollinations": {"base_url": "https://text.pollinations.ai/openai", "model": "openai", "api_key": ""},
            "claude_cli": {"command": "claude", "model": ""},
            "ollama": {"base_url": "http://127.0.0.1:11434", "model": "llama3.1"},
            "gemini": {"model": "gemini-2.5-flash", "api_key": ""},
            "openai_compat": {
                "base_url": "https://openrouter.ai/api/v1",
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "api_key": "",
            },
            "anthropic": {"model": "claude-opus-5-5", "api_key": ""},
        },
    },
    "image_ai": {
        # pollinations | a1111 | none
        "provider": "pollinations",
        "a1111_url": "http://127.0.0.1:7860",
        "pollinations_model": "flux",
    },
    "bg": {
        # auto — нейросеть rembg, если установлена, иначе алгоритм | ai | algo
        "engine": "auto", "model": "isnet-anime", "second": "isnet-general-use", "matting": False, "defringe": True,
    },
    "telegram": {
        "api_id": "",
        "api_hash": "",
        "phone": "",
        "bot_token": "",
        "user_id": "",
    },
    "translations": {
        "headless": False,
    },
}

_lock = threading.Lock()


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> dict:
    with _lock:
        if SETTINGS_FILE.exists():
            try:
                stored = json.loads(SETTINGS_FILE.read_text("utf-8"))
            except json.JSONDecodeError:
                stored = {}
        else:
            stored = {}
        return _deep_merge(DEFAULTS, stored)


def save_settings(patch: dict) -> dict:
    current = load_settings()
    merged = _deep_merge(current, patch)
    with _lock:
        SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")
    return merged


def public_settings() -> dict:
    """Настройки для фронтенда: ключи API маскируются."""
    s = load_settings()
    for p in s["ai"]["providers"].values():
        if p.get("api_key"):
            p["api_key"] = "•••" + p["api_key"][-4:]
    tg = s["telegram"]
    if tg.get("api_hash"):
        tg["api_hash"] = "•••" + tg["api_hash"][-4:]
    if tg.get("bot_token"):
        tg["bot_token"] = "•••" + tg["bot_token"][-4:]
    return s


def strip_masked(patch: dict) -> dict:
    """Не перезаписывать сохранённые секреты маской '•••xxxx' из UI."""
    def walk(d):
        if not isinstance(d, dict):
            return d
        return {k: walk(v) for k, v in d.items()
                if not (isinstance(v, str) and v.startswith("•••"))}
    return walk(patch)
