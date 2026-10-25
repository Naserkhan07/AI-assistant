"""Plugin/skill loader — isolated, permission-gated, hot-reloadable."""
from .loader import PluginManager, Plugin

__all__ = ["PluginManager", "Plugin"]
