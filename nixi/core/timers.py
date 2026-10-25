"""Timer & reminder — platform-safe beep, optional persistence."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

from nixi.config import NixiConfig, get_config
from nixi.platform.system import beep


class TimerItem:
    def __init__(self, duration_sec: int, label: str,
                 on_complete: Callable[[str], None] | None = None):
        self.duration_sec = duration_sec
        self.label = label
        self.remaining = duration_sec
        self.on_complete = on_complete
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"Timer:{label}")
        self.thread.start()

    def _run(self) -> None:
        while self.remaining > 0 and self.is_running:
            time.sleep(1)
            self.remaining -= 1
        if self.is_running:
            for _ in range(3):
                try:
                    beep(1000, 250)
                except Exception:
                    pass
                time.sleep(0.15)
            if self.on_complete:
                try:
                    self.on_complete(self.label)
                except Exception:
                    pass

    def cancel(self) -> None:
        self.is_running = False


class TimerManager:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()
        self.active_timers: list[TimerItem] = []
        if self.config.timers_persist:
            self._restore()

    def add_timer(self, duration_sec: int, label: str,
                  on_complete: Callable[[str], None] | None = None) -> TimerItem:
        item = TimerItem(duration_sec, label, on_complete)
        self.active_timers.append(item)
        if self.config.timers_persist:
            self._save()
        return item

    def cancel_all(self) -> None:
        for t in self.active_timers:
            t.cancel()
        self.active_timers.clear()
        if self.config.timers_persist:
            self._save()

    def list_timers(self) -> list[dict[str, Any]]:
        return [{"label": t.label, "remaining": t.remaining, "duration": t.duration_sec,
                 "running": t.is_running} for t in self.active_timers]

    def _save(self) -> None:
        try:
            path = Path(self.config.data_dir) / "timers.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [{"label": t.label, "remaining": t.remaining, "duration": t.duration_sec}
                    for t in self.active_timers if t.is_running]
            path.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    def _restore(self) -> None:
        try:
            path = Path(self.config.data_dir) / "timers.json"
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data:
                remaining = int(entry.get("remaining", 0))
                if remaining > 0:
                    self.add_timer(remaining, entry.get("label", "restored timer"))
        except (OSError, ValueError, KeyError):
            pass
