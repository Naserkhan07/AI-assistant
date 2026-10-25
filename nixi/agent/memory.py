"""Long-term memory engine — SQLite-backed, config-driven, PII-aware."""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from nixi.config import NixiConfig, get_config
from nixi.privacy.vision_guard import redact_pii
from nixi.logging_utils import get_logger

log = get_logger("memory")


class AgentMemory:
    def __init__(self, db_path: str | Path | None = None, config: NixiConfig | None = None):
        self.config = config or get_config()
        if db_path:
            self.db_path = str(Path(db_path).expanduser())
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self.db_path = str(self.config.data_path("memory.db"))
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL, value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    updated_at REAL DEFAULT (strftime('%s','now'))
                )""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL, status TEXT NOT NULL,
                    steps_count INTEGER DEFAULT 0, summary TEXT,
                    created_at REAL DEFAULT (strftime('%s','now'))
                )""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL, content TEXT NOT NULL,
                    created_at REAL DEFAULT (strftime('%s','now'))
                )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at)")
            conn.commit()
        if not self.get_fact("user_name"):
            self.set_fact("user_name", self.config.user_name or "Sir", "profile")
        if not self.get_fact("assistant_name"):
            self.set_fact("assistant_name", self.config.assistant_name or "Nixi", "profile")

    # ── facts ─────────────────────────────────────────────────────────────
    def set_fact(self, key: str, value: str, category: str = "general") -> bool:
        clean_key = key.strip().lower().replace(" ", "_")[:80]
        # redact obvious secrets before persisting
        clean_val = redact_pii(value.strip())[:2000]
        try:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO user_facts (key, value, category, updated_at)
                    VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value, category=excluded.category, updated_at=excluded.updated_at
                """, (clean_key, clean_val, category, time.time()))
                conn.commit()
            return True
        except Exception as exc:
            log.warning("set_fact error: %s", exc)
            return False

    def get_fact(self, key: str) -> str | None:
        clean_key = key.strip().lower().replace(" ", "_")
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT value FROM user_facts WHERE key=? LIMIT 1", (clean_key,)).fetchone()
                return row["value"] if row else None
        except Exception:
            return None

    def search_facts(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        pat = f"%{query.strip().lower()}%"
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT key, value, category, updated_at FROM user_facts "
                    "WHERE key LIKE ? OR value LIKE ? OR category LIKE ? ORDER BY updated_at DESC LIMIT ?",
                    (pat, pat, pat, limit))
                return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []

    def get_all_facts(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(
                    "SELECT key, value, category, updated_at FROM user_facts ORDER BY category, key").fetchall()]
        except Exception:
            return []

    def delete_fact(self, key: str) -> bool:
        clean_key = key.strip().lower().replace(" ", "_")
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM user_facts WHERE key=?", (clean_key,))
                conn.commit()
            return True
        except Exception:
            return False

    def get_system_context_prompt(self, max_items: int = 12) -> str:
        facts = self.get_all_facts()
        if not facts:
            return ""
        lines = ["--- Persistent User Knowledge & Context ---"]
        for f in facts[:max_items]:
            lines.append(f"• {f['key'].replace('_',' ').title()}: {f['value']}")
        lines.append("------------------------------------------")
        return "\n".join(lines)

    def try_extract_memory(self, prompt: str) -> tuple[str, str] | None:
        m = re.search(r"\b(?:remember|note|save)\s+(?:that\s+)?(?:my\s+)?(.+?)\s+(?:is|are|=|to\s+be)\s+(.+)$",
                      prompt, re.IGNORECASE)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip().rstrip(".!?,")
            if len(k) > 2 and len(v) > 0 and len(k) < 80:
                # never persist things that look like secrets
                if any(s in k.lower() or s in v.lower() for s in ("password", "secret", "api_key", "token", "sk-")):
                    return None
                self.set_fact(k, v, "preferences")
                return k, v
        return None

    # ── task history ───────────────────────────────────────────────────────
    def log_task(self, goal: str, status: str, steps_count: int, summary: str) -> None:
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO task_history (goal, status, steps_count, summary, created_at) VALUES (?,?,?,?,?)",
                             (goal, status, steps_count, summary[:2000], time.time()))
                conn.commit()
        except Exception as exc:
            log.warning("log_task error: %s", exc)

    def recent_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(
                    "SELECT * FROM task_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
        except Exception:
            return []

    # ── conversation history ───────────────────────────────────────────────
    def add_message(self, role: str, content: str) -> None:
        if not content or not content.strip():
            return
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO conversations (role, content, created_at) VALUES (?,?,?)",
                             (role, content.strip()[:4000], time.time()))
                # cap at 500 messages
                conn.execute("DELETE FROM conversations WHERE id NOT IN (SELECT id FROM conversations ORDER BY id DESC LIMIT 500)")
                conn.commit()
        except Exception as exc:
            log.warning("add_message error: %s", exc)

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT role, content, created_at FROM conversations ORDER BY id ASC LIMIT ?",
                                    (limit,)).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def clear_history(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM conversations")
                conn.commit()
        except Exception:
            pass
