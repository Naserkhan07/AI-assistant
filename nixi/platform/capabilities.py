"""Runtime capability detection (never raises, never imports heavy libraries)."""
from __future__ import annotations

import importlib.util
import os
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
HAS_GUI = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or IS_WINDOWS or IS_MACOS)


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def capability_report() -> dict[str, bool]:
    """Which optional subsystems are genuinely available on this machine."""
    return {
        "windows": IS_WINDOWS,
        "macos": IS_MACOS,
        "linux": IS_LINUX,
        "gui": HAS_GUI,
        "qt": has_module("PyQt6"),
        "pillow": has_module("PIL"),
        "numpy": has_module("numpy"),
        "sounddevice": has_module("sounddevice"),
        "soundfile": has_module("soundfile"),
        "faster_whisper": has_module("faster_whisper"),
        "edge_tts": has_module("edge_tts"),
        "pyautogui": has_module("pyautogui"),
        "pyperclip": has_module("pyperclip"),
        "psutil": has_module("psutil"),
        "httpx": has_module("httpx"),
        "playwright": has_module("playwright"),
        "feedparser": has_module("feedparser"),
        "pywin32": has_module("win32com"),
        "sqlite_fts5": _has_fts5(),
    }


def _has_fts5() -> bool:
    import sqlite3
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        conn.close()
        return True
    except Exception:
        return False
