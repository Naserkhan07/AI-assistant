"""
Nixi Screen Reader & Vision Engine — High-Speed Edition
Captures screen in <15ms with optimized bilinear scaling and compact JPEG payload.
"""
from __future__ import annotations

import io
from PIL import Image

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

from PIL import ImageGrab

class ScreenReader:
    @staticmethod
    def capture_screen(max_dimension: int = 800) -> bytes:
        """Capture screen and return compact JPEG bytes scaled for ultra-fast vision inference."""
        img: Image.Image
        if HAS_MSS:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[1]  # primary monitor
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception:
                img = ImageGrab.grab()
        else:
            img = ImageGrab.grab()

        # Fast Bilinear scaling
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=65, optimize=False)
        return buf.getvalue()
