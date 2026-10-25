"""Notification center — in-memory + persisted JSON, respects config."""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger
log = get_logger("notifications")
class NotificationCenter:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()
        self.path = Path(self.config.data_dir) / "notifications.json"
        self._items: list[dict[str, Any]] = self._load()
    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists(): return []
        try: data=json.loads(self.path.read_text(encoding="utf-8")); return data if isinstance(data, list) else []
        except Exception: return []
    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            keep = self.config.notification_history
            self.path.write_text(json.dumps(self._items[-keep:], indent=2), encoding="utf-8")
        except Exception: pass
    def push(self, title: str, body: str = "", kind: str = "info", meta: dict | None = None) -> dict[str, Any]:
        item={"id": int(time.time()*1000), "title": title, "body": body, "kind": kind, "meta": meta or {}, "ts": time.time(), "read": False}
        self._items.append(item); self._save()
        log.info("Notification [%s] %s", kind, title)
        return item
    def all(self, limit: int | None = None) -> list[dict[str, Any]]:
        items = list(reversed(self._items))
        return items[:limit] if limit else items
    def mark_read(self, nid: int) -> None:
        for it in self._items: 
            if it["id"]==nid: it["read"]=True
        self._save()
    def mark_all_read(self) -> None:
        for it in self._items: it["read"]=True
        self._save()
    def unread_count(self) -> int: return sum(1 for it in self._items if not it.get("read"))
    def clear(self) -> None: self._items=[]; self._save()
