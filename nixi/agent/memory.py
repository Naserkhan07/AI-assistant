"""
Nixi Agent Long-Term Memory Engine (SQLite-backed)
Provides persistent cross-session memory for user facts, project preferences,
interaction history, and context recall.
"""
from __future__ import annotations

import os
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class AgentMemory:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            base_dir = Path(__file__).resolve().parent.parent.parent / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(base_dir / "memory.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create tables for persistent facts, preferences, and task histories."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    steps_count INTEGER DEFAULT 0,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

        # Seed default assistant & user identity if not already present
        if not self.get_fact("user_name"):
            self.set_fact("user_name", "Sir", "profile")
        if not self.get_fact("assistant_name"):
            self.set_fact("assistant_name", "Nixi", "profile")

    def set_fact(self, key: str, value: str, category: str = "general") -> bool:
        """Store or update a key-value fact in persistent memory."""
        clean_key = key.strip().lower().replace(" ", "_")
        clean_val = value.strip()
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO user_facts (key, value, category, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        category = excluded.category,
                        updated_at = CURRENT_TIMESTAMP;
                """, (clean_key, clean_val, category))
                conn.commit()
            return True
        except Exception as e:
            print(f"[Nixi Memory] Error saving fact '{clean_key}': {e}")
            return False

    def get_fact(self, key: str) -> Optional[str]:
        """Retrieve a specific fact by key."""
        clean_key = key.strip().lower().replace(" ", "_")
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT value FROM user_facts WHERE key = ? LIMIT 1;", (clean_key,))
                row = cur.fetchone()
                return row["value"] if row else None
        except Exception:
            return None

    def search_facts(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fuzzy search across stored facts."""
        clean_q = f"%{query.strip().lower()}%"
        try:
            with self._get_connection() as conn:
                cur = conn.execute("""
                    SELECT key, value, category, updated_at
                    FROM user_facts
                    WHERE key LIKE ? OR value LIKE ? OR category LIKE ?
                    ORDER BY updated_at DESC LIMIT ?;
                """, (clean_q, clean_q, clean_q, limit))
                return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def get_all_facts(self) -> List[Dict[str, Any]]:
        """Return all stored facts."""
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT key, value, category, updated_at FROM user_facts ORDER BY category, key;")
                return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def delete_fact(self, key: str) -> bool:
        """Delete a fact from memory."""
        clean_key = key.strip().lower().replace(" ", "_")
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM user_facts WHERE key = ?;", (clean_key,))
                conn.commit()
            return True
        except Exception:
            return False

    def get_system_context_prompt(self, max_items: int = 12) -> str:
        """Format persistent facts into a compact context block for the LLM."""
        facts = self.get_all_facts()
        if not facts:
            return ""

        lines = ["--- Persistent User Knowledge & Context ---"]
        for f in facts[:max_items]:
            display_k = f["key"].replace("_", " ").title()
            lines.append(f"• {display_k}: {f['value']}")
        lines.append("------------------------------------------")
        return "\n".join(lines)

    def try_extract_memory(self, prompt: str) -> Optional[Tuple[str, str]]:
        """
        Detects if user said e.g.:
        - 'remember that my favorite language is Python'
        - 'remember my email is test@domain.com'
        - 'note that I prefer dark mode'
        Returns: (key, value) if extracted and stored, else None.
        """
        match = re.search(r"\b(?:remember|note|save)\s+(?:that\s+)?(?:my\s+)?(.+?)\s+(?:is|are|=|to\s+be)\s+(.+)$", prompt, re.IGNORECASE)
        if match:
            k = match.group(1).strip()
            v = match.group(2).strip().rstrip(".!?,")
            # Filter common words
            if len(k) > 2 and len(v) > 0:
                self.set_fact(k, v, "preferences")
                return k, v
        return None

    def log_task(self, goal: str, status: str, steps_count: int, summary: str):
        """Log an autonomous agent task into history."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO task_history (goal, status, steps_count, summary)
                    VALUES (?, ?, ?, ?);
                """, (goal, status, steps_count, summary))
                conn.commit()
        except Exception as e:
            print(f"[Nixi Memory] Task log error: {e}")
