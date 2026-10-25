"""Deterministic no-op stand-ins used when optional desktop libraries are missing.

They are intentionally *safe*: they never touch the filesystem, network, keyboard
or clipboard of the host machine. This is what makes headless/CI mode possible.
"""
from __future__ import annotations

import math
import time
from types import SimpleNamespace
from typing import Any, Iterable, Iterator


class FakePyAutoGUI:
    FAILSAFE = True
    PAUSE = 0.0

    def size(self) -> tuple[int, int]:
        return (1920, 1080)

    def position(self) -> tuple[int, int]:
        return (0, 0)

    def __getattr__(self, name: str):
        def _noop(*args: Any, **kwargs: Any) -> None:
            return None

        return _noop


class FakePyperclip:
    def __init__(self) -> None:
        self._clip = ""

    def copy(self, text: str) -> None:
        self._clip = str(text)

    def paste(self) -> str:
        return self._clip

    def waitForPaste(self, timeout: float = 1.0) -> str:
        return self._clip


class FakePsutil:
    """Small, truthful-enough psutil stand-in."""

    @staticmethod
    def cpu_percent(interval: float | None = None) -> float:
        return 0.0

    @staticmethod
    def virtual_memory() -> SimpleNamespace:
        return SimpleNamespace(total=8 * 1024**3, used=4 * 1024**3, percent=50.0)

    @staticmethod
    def disk_usage(path: str = "/") -> SimpleNamespace:
        return SimpleNamespace(total=256 * 1024**3, used=128 * 1024**3, free=128 * 1024**3, percent=50.0)

    @staticmethod
    def sensors_battery() -> None:
        return None

    @staticmethod
    def process_iter(attrs: Iterable[str] | None = None) -> Iterator[SimpleNamespace]:
        return iter(())

    class NoSuchProcess(Exception):
        pass

    class AccessDenied(Exception):
        pass


class FakeNumpy:
    """Only the surface Nixi uses; adequate for import-time type annotations."""

    ndarray = list
    float32 = float
    int16 = int
    bool_ = bool

    @staticmethod
    def sqrt(value: float) -> float:
        return math.sqrt(value)

    @staticmethod
    def mean(values: Any) -> float:
        seq = list(values)
        return sum(seq) / len(seq) if seq else 0.0

    @staticmethod
    def concatenate(chunks: Iterable[Any]) -> list:
        out: list = []
        for chunk in chunks:
            out.extend(chunk)
        return out

    @staticmethod
    def array(values: Any, dtype: Any = None) -> list:
        return list(values)


class _FakeStream:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def close(self) -> None:
        self.started = False

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


class FakeSoundDevice:
    InputStream = _FakeStream

    @staticmethod
    def play(*args: Any, **kwargs: Any) -> None:
        return None

    @staticmethod
    def stop() -> None:
        return None

    @staticmethod
    def wait() -> None:
        return None

    @staticmethod
    def query_devices(*args: Any, **kwargs: Any) -> list:
        return []


class FakeSoundFile:
    @staticmethod
    def read(*args: Any, **kwargs: Any) -> tuple[list, int]:
        return ([], 24000)


class FakeWinSound:
    @staticmethod
    def Beep(frequency: int, duration: int) -> None:
        return None

    @staticmethod
    def PlaySound(*args: Any, **kwargs: Any) -> None:
        return None


class FakePILImage:
    class Resampling:
        BILINEAR = 2
        LANCZOS = 1

    @staticmethod
    def open(*args: Any, **kwargs: Any):
        raise RuntimeError("Pillow is unavailable")

    @staticmethod
    def frombytes(*args: Any, **kwargs: Any):
        raise RuntimeError("Pillow is unavailable")

    @staticmethod
    def new(*args: Any, **kwargs: Any):
        raise RuntimeError("Pillow is unavailable")


def sleep(_seconds: float) -> None:
    """Exposed for tests that want to patch time.sleep."""
    time.sleep(_seconds)
