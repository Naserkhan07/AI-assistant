"""Import third-party / OS-specific packages without ever crashing at import time.

Nixi runs a real desktop on Windows, but must also be importable (and testable)
on Linux/macOS and in CI where PyAudio, pyautogui, psutil, Qt, etc. are absent.
"""
from __future__ import annotations

import importlib
import importlib.util
from typing import Any


class _MissingCallable:
    """Callable that always returns None; used for unknown attributes."""

    __slots__ = ("_owner", "_name")

    def __init__(self, owner: str, name: str):
        self._owner = owner
        self._name = name

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        return None

    def __getattr__(self, item: str) -> "_MissingCallable":
        return _MissingCallable(self._owner, f"{self._name}.{item}")

    def __repr__(self) -> str:
        return f"<unavailable {self._owner}.{self._name}>"


class NullModule:
    """Stand-in for an unavailable module. Any attribute access is harmless."""

    def __init__(self, name: str, **attrs: Any):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_attrs", dict(attrs))

    def __getattr__(self, item: str) -> Any:
        attrs = object.__getattribute__(self, "_attrs")
        if item in attrs:
            return attrs[item]
        return _MissingCallable(object.__getattribute__(self, "_name"), item)

    def __setattr__(self, key: str, value: Any) -> None:
        object.__getattribute__(self, "_attrs")[key] = value

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<NullModule {object.__getattribute__(self, '_name')}>"


def load(name: str, fake: Any = None) -> Any:
    """Return the real module, or ``fake`` / a :class:`NullModule` if uninstalled."""
    try:
        return importlib.import_module(name)
    except Exception:
        return fake if fake is not None else NullModule(name)


def is_available(module: Any) -> bool:
    """True when ``module`` is the real library rather than a compatibility fake."""
    return not isinstance(module, (NullModule,)) and module is not None and bool(module)
