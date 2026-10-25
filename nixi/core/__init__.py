"""Nixi Core Package — lazy, headless-safe."""
from .llm_client import NixiLLMClient as NixiLLMClient

try:
    from .dictation import DictationManager as DictationManager
except ImportError:
    DictationManager = None  # type: ignore
try:
    from .screen_reader import ScreenReader as ScreenReader
except ImportError:
    ScreenReader = None  # type: ignore
try:
    from .app_launcher import AppLauncher as AppLauncher
except ImportError:
    AppLauncher = None  # type: ignore
try:
    from .timers import TimerManager as TimerManager
except ImportError:
    TimerManager = None  # type: ignore
