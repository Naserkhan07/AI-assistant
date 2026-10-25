"""Dictation engine — clipboard injection with safe fallbacks."""
from __future__ import annotations

import time
import threading

from nixi.compat.optional import load
from nixi.compat import fakes

pyautogui = load("pyautogui", fakes.FakePyAutoGUI())
pyperclip = load("pyperclip", fakes.FakePyperclip())


class DictationManager:
    def __init__(self):
        self.is_active = False
        self._lock = threading.Lock()

    def toggle(self) -> bool:
        with self._lock:
            self.is_active = not self.is_active
            return self.is_active

    def set_active(self, active: bool) -> None:
        with self._lock:
            self.is_active = active

    def inject_text(self, text: str, trailing_space: bool = True) -> None:
        if not text or not text.strip():
            return
        cleaned = text.strip() + (" " if trailing_space else "")
        old_clip = ""
        try:
            old_clip = pyperclip.paste()
        except Exception:
            pass
        try:
            pyperclip.copy(cleaned)
            time.sleep(0.04)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)
        except Exception:
            try:
                pyautogui.write(cleaned, interval=0.01)
            except Exception:
                pass
        finally:
            time.sleep(0.1)
            if old_clip:
                try:
                    pyperclip.copy(old_clip)
                except Exception:
                    pass
