"""Thread-safe in-memory task center with cooperative cancellation."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskRecord:
    task_id: str
    title: str
    state: str = "active"
    progress: int = 0
    detail: str = "Queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "state": self.state,
            "progress": self.progress,
            "detail": self.detail,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "cancel_requested": self.cancel_event.is_set(),
        }


class TaskCenter:
    """Tracks active/recent actions and exposes cooperative cancellation events."""
    def __init__(self, history_limit: int = 50):
        self.history_limit = max(10, int(history_limit))
        self._lock = threading.RLock()
        self._tasks: dict[str, TaskRecord] = {}
        self._order: list[str] = []

    def start(self, title: str) -> str:
        task_id = uuid.uuid4().hex[:8]
        record = TaskRecord(task_id=task_id, title=(title or "Task")[:180])
        with self._lock:
            self._tasks[task_id] = record
            self._order.append(task_id)
            self._trim_locked()
        return task_id

    def update(self, task_id: str, detail: str, progress: int | None = None) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            if not record or record.state != "active":
                return False
            record.detail = str(detail)[:300]
            if progress is not None:
                record.progress = max(0, min(100, int(progress)))
            record.updated_at = time.time()
            return True

    def finish(self, task_id: str, result: str = "", failed: bool = False) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            if not record or record.state != "active":
                return False
            record.state = "cancelled" if record.cancel_event.is_set() else ("failed" if failed else "completed")
            record.progress = 100 if record.state == "completed" else record.progress
            record.detail = record.state.title()
            record.result = str(result)[:1000]
            record.updated_at = time.time()
            return True

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            if not record or record.state != "active":
                return False
            record.cancel_event.set()
            record.detail = "Cancellation requested; finishing current safe step"
            record.updated_at = time.time()
            return True

    def cancel_latest(self) -> str | None:
        with self._lock:
            for task_id in reversed(self._order):
                record = self._tasks[task_id]
                if record.state == "active":
                    record.cancel_event.set()
                    record.detail = "Cancellation requested; finishing current safe step"
                    record.updated_at = time.time()
                    return task_id
        return None

    def cancel_event(self, task_id: str) -> threading.Event | None:
        with self._lock:
            record = self._tasks.get(task_id)
            return record.cancel_event if record else None

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._tasks[k].as_dict() for k in reversed(self._order) if k in self._tasks]

    def _trim_locked(self) -> None:
        while len(self._order) > self.history_limit:
            oldest = self._order[0]
            record = self._tasks.get(oldest)
            if record and record.state == "active":
                break
            self._order.pop(0)
            self._tasks.pop(oldest, None)
