"""
Nixi Dictation Engine
Types transcribed text directly into whichever desktop application currently has keyboard focus.
Uses fast clipboard injection (Ctrl+V) with fallback to keyboard typing to support full Unicode & emojis.
"""
from __future__ import annotations

import time
import threading
import pyautogui
import pyperclip

class DictationManager:
    def __init__(self):
        self.is_active = False
        self._lock = threading.Lock()

    def toggle(self) -> bool:
        with self._lock:
            self.is_active = not self.is_active
            return self.is_active

    def set_active(self, active: bool):
        with self._lock:
            self.is_active = active

    def inject_text(self, text: str, trailing_space: bool = True):
        """Injects text into active window via clipboard Ctrl+V."""
        if not text:
            return

        cleaned_text = text.strip()
        if not cleaned_text:
            return

        if trailing_space:
            cleaned_text += " "

        # Save previous clipboard content
        old_clip = ""
        try:
            old_clip = pyperclip.paste()
        except Exception:
            pass

        try:
            # Put text in clipboard and simulate Ctrl+V
            pyperclip.copy(cleaned_text)
            time.sleep(0.04)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.05)
        except Exception as e:
            # Fallback to direct typing
            try:
                pyautogui.write(cleaned_text, interval=0.01)
            except Exception:
                pass
        finally:
            # Restore clipboard after small delay
            time.sleep(0.1)
            if old_clip:
                try:
                    pyperclip.copy(old_clip)
                except Exception:
                    pass
