"""
Nixi Screen Reader & Vision Engine — High-Speed Multi-Backend Edition
Captures screen in <15ms with multi-layer fallback:
1. Native Qt Window grab (QApplication primaryScreen - 100% reliable in GUI)
2. MSS high-speed direct monitor capture
3. PIL ImageGrab (all_screens=True)
4. PyAutoGUI screenshot
"""
from __future__ import annotations

import io
from PIL import Image

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

import time
import ctypes
from ctypes import wintypes
from PIL import ImageGrab


_GLOBAL_WINSTA0 = None
_GLOBAL_DESK = None


def _ensure_desktop_access():
    """Ensure the calling thread is attached to the interactive Windows desktop."""
    global _GLOBAL_WINSTA0, _GLOBAL_DESK
    try:
        user32 = ctypes.windll.user32
        user32.OpenWindowStationW.restype = wintypes.HANDLE
        user32.OpenDesktopW.restype = wintypes.HANDLE

        _GLOBAL_WINSTA0 = user32.OpenWindowStationW("winsta0", False, 0x037F)
        if _GLOBAL_WINSTA0:
            user32.SetProcessWindowStation(_GLOBAL_WINSTA0)
        _GLOBAL_DESK = user32.OpenDesktopW("default", 0, False, 0x01FF)
        if _GLOBAL_DESK:
            user32.SetThreadDesktop(_GLOBAL_DESK)
    except Exception:
        pass


# Ensure desktop access immediately upon import
_ensure_desktop_access()


class ScreenReader:
    @staticmethod
    def capture_screen(max_dimension: int = 900) -> bytes:
        """Capture screen and return compact JPEG bytes scaled for ultra-fast vision inference."""
        _ensure_desktop_access()

        # Backend 1: PIL ImageGrab (direct full desktop capture with retry)
        img: Image.Image | None = None
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

        # Backend 2: Native Qt primary screen grab (if inside PyQt6 GUI loop)
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
                                if pixmap.width() >= pixmap.height():
                                    pixmap = pixmap.scaledToWidth(max_dimension)
                                else:
                                    pixmap = pixmap.scaledToHeight(max_dimension)
                            buf = QBuffer()
                            buf.open(QIODevice.OpenModeFlag.WriteOnly)
                            pixmap.save(buf, "JPEG", 75)
                            data = bytes(buf.data())
                            if len(data) > 500:
                                return data
            except Exception:
                pass

        # Backend 3: MSS Monitor Grab
        if img is None and HAS_MSS:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[1]  # primary monitor
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception:
                img = None

        # Backend 3: PIL ImageGrab
        if img is None:
            try:
                img = ImageGrab.grab(all_screens=True)
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

        # Bilinear scaling for minimal tokens & maximum LLM speed
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70, optimize=False)
        return buf.getvalue()
