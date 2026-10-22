"""Запуск TG Studio: python run.py  → откроется http://127.0.0.1:8765"""
import argparse
import threading
import webbrowser

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TG Studio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"\n  ✦ TG Studio запущен: {url}\n  (закрой окно / Ctrl+C чтобы остановить)\n")
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="warning")
