"""Screen reader — multi-backend, headless-safe."""
from __future__ import annotations

import io
import time
import ctypes
from ctypes import wintypes

from nixi.compat.optional import load
from nixi.compat import fakes

PIL_Image = load("PIL.Image", None)
ImageGrab = load("PIL.ImageGrab", None)
mss_mod = load("mss", None)
HAS_MSS = mss_mod is not None and not isinstance(mss_mod, type(load("nope")))

try:
    import mss as _mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

_GLOBAL_WINSTA0 = None
_GLOBAL_DESK = None

def _ensure_desktop_access() -> None:
    global _GLOBAL_WINSTA0, _GLOBAL_DESK
    try:
        user32 = ctypes.windll.user32  # type: ignore
        user32.OpenWindowStationW.restype = wintypes.HANDLE  # type: ignore
        user32.OpenDesktopW.restype = wintypes.HANDLE  # type: ignore
        _GLOBAL_WINSTA0 = user32.OpenWindowStationW("winsta0", False, 0x037F)
        if _GLOBAL_WINSTA0:
            user32.SetProcessWindowStation(_GLOBAL_WINSTA0)
        _GLOBAL_DESK = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if _GLOBAL_DESK:
            user32.SetThreadDesktop(_GLOBAL_DESK)
    except Exception:
        pass

try:
    _ensure_desktop_access()
except Exception:
    pass


class ScreenReader:
    @staticmethod
    def capture_screen(max_dimension: int = 900) -> bytes:
        if PIL_Image is None or isinstance(PIL_Image, type(load("nope"))):
            # No PIL — try Qt fallback, then give up gracefully
            try:
                from PyQt6.QtWidgets import QApplication
                from PyQt6.QtCore import QBuffer, QIODevice
                app = QApplication.instance()
                if app:
                    screen = QApplication.primaryScreen()
                    if screen:
                        pixmap = screen.grabWindow(0)
                        if not pixmap.isNull() and pixmap.width() > 0:
                            if max(pixmap.width(), pixmap.height()) > max_dimension:
                                pixmap = pixmap.scaledToWidth(max_dimension) if pixmap.width() >= pixmap.height() else pixmap.scaledToHeight(max_dimension)
                            buf = QBuffer(); buf.open(QIODevice.OpenModeFlag.WriteOnly)
                            pixmap.save(buf, "JPEG", 75)
                            data = bytes(buf.data())
                            if len(data) > 500:
                                return data
            except Exception:
                pass
            return b""

        _ensure_desktop_access()
        img = None
        # Backend 1: ImageGrab
        if ImageGrab is not None and not isinstance(ImageGrab, type(load("nope"))):
            for _ in range(2):
                try:
                    img = ImageGrab.grab(all_screens=True)
                    if img:
                        break
                except Exception:
                    try:
                        img = ImageGrab.grab()
                        if img:
                            break
                    except Exception:
                        time.sleep(0.04)
        # Backend 2: Qt
        if img is None:
            try:
                from PyQt6.QtWidgets import QApplication
                from PyQt6.QtCore import QBuffer, QIODevice
                app = QApplication.instance()
                if app:
                    screen = QApplication.primaryScreen()
                    if screen:
                        pixmap = screen.grabWindow(0)
                        if not pixmap.isNull() and pixmap.width() > 0 and pixmap.height() > 0:
                            if max(pixmap.width(), pixmap.height()) > max_dimension:
                                pixmap = pixmap.scaledToWidth(max_dimension) if pixmap.width() >= pixmap.height() else pixmap.scaledToHeight(max_dimension)
                            buf = QBuffer(); buf.open(QIODevice.OpenModeFlag.WriteOnly)
                            pixmap.save(buf, "JPEG", 75)
                            data = bytes(buf.data())
                            if len(data) > 500:
                                return data
            except Exception:
                pass
        # Backend 3: MSS
        if img is None and HAS_MSS:
            try:
                import mss
                with mss.mss() as sct:
                    sct_img = sct.grab(sct.monitors[1])
                    img = PIL_Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception:
                img = None
        # Backend 4: PyAutoGUI
        if img is None:
            try:
                import pyautogui
                img = pyautogui.screenshot()
            except Exception:
                img = None
        if img is None:
            return b""
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            img = img.resize((int(w*scale), int(h*scale)), PIL_Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70, optimize=False)
        return buf.getvalue()
