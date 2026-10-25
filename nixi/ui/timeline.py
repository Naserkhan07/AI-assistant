"""Activity timeline — reads from audit log + memory tasks."""
from __future__ import annotations
from typing import Any
from nixi.security import ActionJournal
from nixi.agent.memory import AgentMemory
from nixi.config import NixiConfig, get_config
class Timeline:
    def __init__(self, config: NixiConfig | None = None):
        self.config = config or get_config()
        self.journal = ActionJournal(enabled=self.config.audit_enabled)
        self.memory = AgentMemory(config=self.config)
    def events(self, limit: int = 50) -> list[dict[str, Any]]:
        audit = self.journal.recent(limit=limit)
        tasks = self.memory.recent_tasks(limit=limit)
        merged: list[dict[str, Any]] = []
        for a in audit: merged.append({"type":"tool","ts":a.get("ts",0),"title":a.get("action",""),"detail":a.get("reason",""),"raw":a})
        for t in tasks: merged.append({"type":"task","ts":t.get("created_at",0),"title":t.get("goal",""),"detail":t.get("summary",""),"raw":t})
        merged.sort(key=lambda x: x.get("ts",0), reverse=True)
        return merged[:limit]
    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q=query.lower()
        return [e for e in self.events(limit=100) if q in e.get("title","").lower() or q in e.get("detail","").lower()][:limit]
