"""
Nixi Timer & Reminder Manager
Manages background countdown timers, sound alerts, and notifications.
"""
from __future__ import annotations

import time
import threading
import winsound
from typing import Callable, Optional, List

class TimerItem:
    def __init__(self, duration_sec: int, label: str, on_complete: Optional[Callable[[str], None]] = None):
        self.duration_sec = duration_sec
        self.label = label
        self.remaining = duration_sec
        self.on_complete = on_complete
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.remaining > 0 and self.is_running:
            time.sleep(1)
            self.remaining -= 1

        if self.is_running:
            # Sound alert: 3 friendly chime beeps
            try:
                for _ in range(3):
                    winsound.Beep(1000, 250)
                    time.sleep(0.1)
            except Exception:
                pass

            if self.on_complete:
                self.on_complete(self.label)

    def cancel(self):
        self.is_running = False

class TimerManager:
    def __init__(self):
        self.active_timers: List[TimerItem] = []

    def add_timer(self, duration_sec: int, label: str, on_complete: Optional[Callable[[str], None]] = None) -> TimerItem:
        t = TimerItem(duration_sec, label, on_complete)
        self.active_timers.append(t)
        return t

    def cancel_all(self):
        for t in self.active_timers:
            t.cancel()
        self.active_timers.clear()
