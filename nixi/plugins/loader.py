"""Discover ``plugins/*.py`` skills, validate their manifest and run them safely."""
from __future__ import annotations

import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger

log = get_logger("plugins")


@dataclass
class Plugin:
    name: str
    version: str
    description: str
    path: Path
    module: Any = None
    enabled: bool = True
    error: str = ""
    tools: dict[str, Callable] = field(default_factory=dict)


class PluginManager:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()
        self.plugins: dict[str, Plugin] = {}

    @property
    def plugins_dir(self) -> Path:
        return Path(self.config.plugins_dir or (Path(self.config.data_dir) / "plugins"))

    def discover(self) -> list[Plugin]:
        self.plugins.clear()
        if not self.config.plugins_enabled:
            return []
        root = self.plugins_dir
        if not root.exists():
            return []
        for file in sorted(root.glob("*.py")):
            if file.name.startswith("_"):
                continue
            plugin = self._load_file(file)
            self.plugins[plugin.name] = plugin
        return list(self.plugins.values())

    def _load_file(self, path: Path) -> Plugin:
        name = path.stem
        plugin = Plugin(name=name, version="0.0.0", description="", path=path)
        try:
            spec = importlib.util.spec_from_file_location(f"nixi.plugins.user.{name}", path)
            if not spec or not spec.loader:
                raise ImportError(f"cannot create spec for {path}")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)  # type: ignore
            plugin.module = mod
            plugin.version = getattr(mod, "__version__", "0.0.0")
            plugin.description = getattr(mod, "__description__", getattr(mod, "__doc__", "") or "")[:200]
            # collect tools: functions decorated with @nixi_tool or plain callables
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if callable(obj) and getattr(obj, "_nixi_tool", False):
                    plugin.tools[attr_name] = obj
            # also auto-expose if module defines TOOLS dict
            if hasattr(mod, "TOOLS") and isinstance(mod.TOOLS, dict):
                for k, v in mod.TOOLS.items():
                    if callable(v):
                        plugin.tools[k] = v
        except Exception:
            plugin.enabled = False
            plugin.error = traceback.format_exc(limit=3)
            log.warning("Plugin %s failed to load: %s", name, plugin.error.splitlines()[-1] if plugin.error else "")
        return plugin

    def call(self, plugin_name: str, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        plugin = self.plugins.get(plugin_name)
        if not plugin or not plugin.enabled:
            return {"ok": False, "error": f"plugin '{plugin_name}' not available"}
        fn = plugin.tools.get(tool_name)
        if not fn:
            return {"ok": False, "error": f"tool '{tool_name}' not found in '{plugin_name}'"}
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            log.warning("Plugin %s.%s error: %s", plugin_name, tool_name, exc)
            return {"ok": False, "error": str(exc)}

    def status(self) -> list[dict[str, Any]]:
        return [
            {"name": p.name, "version": p.version, "enabled": p.enabled,
             "description": p.description, "tools": list(p.tools.keys()), "error": p.error}
            for p in self.plugins.values()
        ]
