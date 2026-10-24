"""
Windows Acrylic & Mica Glassmorphism Helper
Applies safe native Windows 11 DWM backdrop blur and immersive dark mode.
"""
import sys
import ctypes
from ctypes import c_int, byref, sizeof

def apply_glassmorphism(hwnd: int, dark_mode: bool = True):
    """Enable native Windows Acrylic/Mica blur and dark mode for a window HWND."""
    if sys.platform != "win32":
        return

    # 1. Enable Immersive Dark Mode (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
    try:
        val = c_int(1 if dark_mode else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(val), sizeof(val))
    except Exception:
        pass

    # 2. Windows 11 System Backdrop (DWMWA_SYSTEMBACKDROP_TYPE = 38)
    # 1 = Auto, 2 = None, 3 = Mica, 4 = Acrylic, 5 = Tabbed
    try:
        backdrop_type = c_int(4)  # Acrylic
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, byref(backdrop_type), sizeof(backdrop_type))
    except Exception:
        pass
