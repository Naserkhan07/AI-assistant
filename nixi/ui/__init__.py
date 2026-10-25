"""Nixi UI — optional Qt, headless-safe."""
try:
    from .dynamic_island import NixiDynamicIsland
    from .pill_window import NixiPillWindow, OrbState
    from .chat_drawer import ChatDrawer
except ImportError:
    NixiDynamicIsland = NixiPillWindow = ChatDrawer = None
    OrbState = None
