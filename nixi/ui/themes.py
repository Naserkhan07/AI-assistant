"""Theme manager — dark / light / high-contrast, font scaling, opacity."""
from __future__ import annotations
from typing import Any
THEMES = {
    "dark": {"bg":"#1a1a2e","fg":"#eaeaea","accent":"#00d4ff","island_bg":"#252547","border":"#3a3a6a","code_bg":"#0f0f23"},
    "light": {"bg":"#f5f5f7","fg":"#1a1a2e","accent":"#0066cc","island_bg":"#ffffff","border":"#d0d0e0","code_bg":"#eeeeef"},
    "high-contrast": {"bg":"#000000","fg":"#ffffff","accent":"#ffff00","island_bg":"#111111","border":"#ffffff","code_bg":"#0a0a0a"},
}
def palette(theme: str) -> dict[str, str]: return THEMES.get(theme, THEMES["dark"])
def css_vars(theme: str, font_scale: float = 1.0, opacity: float = 0.96) -> str:
    p = palette(theme)
    return f":root{{--bg:{p['bg']};--fg:{p['fg']};--accent:{p['accent']};--island:{p['island_bg']};--border:{p['border']};--code:{p['code_bg']};--scale:{font_scale};--opacity:{opacity}}}"
