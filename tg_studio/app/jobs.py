"""Фоновые задачи с прогрессом (генерация языков, загрузка паков и т.п.)."""
from __future__ import annotations

import asyncio
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class Job:
    id: str
    title: str
    status: str = "running"  # running | done | error
    progress: float = 0.0
    message: str = ""
    log: list[str] = field(default_factory=list)
    result: Any = None
    started: float = field(default_factory=time.time)
    waiting: str = ""  # текст подсказки, если задача ждёт действия пользователя
    _event: asyncio.Event | None = field(default=None, repr=False)

    def update(self, progress: float | None = None, message: str | None = None):
        if progress is not None:
            self.progress = max(0.0, min(1.0, progress))
        if message:
            self.message = message
            self.log.append(f"[{time.strftime('%H:%M:%S')}] {message}")
            self.log = self.log[-300:]

    async def wait_user(self, hint: str, timeout: float = 900):
        """Пауза до нажатия «Продолжить» в интерфейсе (ручной шаг в браузере)."""
        self._event = asyncio.Event()
        self.waiting = hint
        self.update(message=f"⏸ {hint}")
        try:
            await asyncio.wait_for(self._event.wait(), timeout)
        finally:
            self.waiting = ""

    def resume(self):
        if self._event:
            self._event.set()

    def as_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "status": self.status,
            "progress": round(self.progress, 4), "message": self.message,
            "log": self.log[-60:], "result": self.result, "waiting": self.waiting,
        }


JOBS: dict[str, Job] = {}


def start_job(title: str, fn: Callable[..., Awaitable[Any]], *args, **kwargs) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], title=title)
    JOBS[job.id] = job

    async def runner():
        try:
            job.result = await fn(job, *args, **kwargs)
            job.status = "done"
            job.progress = 1.0
            job.update(message="Готово ✓")
        except Exception as e:  # noqa: BLE001 — показываем ошибку в UI
            job.status = "error"
            job.update(message=f"Ошибка: {e}")
            job.log.append(traceback.format_exc()[-2000:])

    asyncio.get_running_loop().create_task(runner())
    return job
