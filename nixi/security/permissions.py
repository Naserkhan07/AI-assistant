"""Risk-gated tool execution with an auditable, reversible action journal."""
from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Mapping

from nixi.config import NixiConfig, get_config
from nixi.logging_utils import get_logger

log = get_logger("security")


class RiskLevel(IntEnum):
    SAFE = 0          # read-only
    MODERATE = 1      # writes inside Nixi's own data dir
    HIGH = 2          # changes user files, runs shell/code, sends data out
    CRITICAL = 3      # deletes, kills processes, pushes to remotes

    @classmethod
    def parse(cls, value: Any) -> "RiskLevel":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(max(0, min(3, value)))
        return {"safe": cls.SAFE, "moderate": cls.MODERATE, "high": cls.HIGH,
                "critical": cls.CRITICAL}.get(str(value).lower(), cls.SAFE)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    needs_confirmation: bool = False
    risk: RiskLevel = RiskLevel.SAFE
    dry_run: bool = False

    def __bool__(self) -> bool:
        return self.allowed


class ActionJournal:
    """SQLite audit log for every tool invocation (opt-out via config)."""

    def __init__(self, db_path: str | Path | None = None, enabled: bool = True):
        self.enabled = enabled
        self.db_path = str(db_path or (get_config().data_path("audit.db")))
        self._lock = threading.Lock()
        if self.enabled:
            self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    action TEXT NOT NULL,
                    risk INTEGER NOT NULL,
                    args TEXT,
                    decision TEXT,
                    reason TEXT,
                    result TEXT
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS undo_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    op TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    undone INTEGER DEFAULT 0
                )""")
                conn.commit()
        except sqlite3.Error as exc:
            log.warning("Audit DB unavailable: %s", exc)

    def record(self, action: str, risk: RiskLevel, args: Mapping[str, Any],
               decision: str, reason: str, result: str = "") -> None:
        if not self.enabled:
            return
        try:
            with self._lock, self._connect() as conn:
                conn.execute("INSERT INTO audit_log (ts, action, risk, args, decision, reason, result) VALUES (?,?,?,?,?,?,?)",
                             (time.time(), action, int(risk), json.dumps(args, default=str)[:4000],
                              decision, reason, str(result)[:2000]))
                conn.commit()
        except (sqlite3.Error, TypeError):
            pass

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error:
            return []

    def add_undo(self, op: str, payload: Mapping[str, Any]) -> int:
        if not self.enabled:
            return 0
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute("INSERT INTO undo_log (ts, op, payload) VALUES (?,?,?)",
                                   (time.time(), op, json.dumps(dict(payload))))
                conn.commit()
                return int(cur.lastrowid or 0)
        except sqlite3.Error:
            return 0

    def pending_undo(self) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(
                    "SELECT * FROM undo_log WHERE undone=0 ORDER BY id DESC").fetchall()]
        except sqlite3.Error:
            return []

    def mark_undone(self, undo_id: int) -> None:
        if not self.enabled:
            return
        try:
            with self._lock, self._connect() as conn:
                conn.execute("UPDATE undo_log SET undone=1 WHERE id=?", (undo_id,))
                conn.commit()
        except sqlite3.Error:
            pass


class PermissionManager:
    """Decides whether a tool call may run, optionally asking the user."""

    def __init__(self, config: NixiConfig | None = None,
                 confirm_callback: Callable[[str, RiskLevel, Mapping[str, Any]], bool] | None = None,
                 journal: ActionJournal | None = None):
        self.config = config or get_config()
        self.confirm_callback = confirm_callback
        self.journal = journal if journal is not None else ActionJournal(enabled=self.config.audit_enabled)
        self.dry_run = self.config.dry_run
        self._session_approvals: set[str] = set()
        self._lock = threading.Lock()

    def evaluate(self, action: str, risk: RiskLevel,
                 args: Mapping[str, Any] | None = None) -> Decision:
        args = dict(args or {})
        risk = RiskLevel.parse(risk)
        denied = set(self.config.denied_tools)
        allowed = set(self.config.allowed_tools)
        base = action.split(".")[-1]

        if action in denied or base in denied:
            d = Decision(False, f"'{action}' is on the deny list", risk=risk)
            self.journal.record(action, risk, args, "denied", d.reason)
            return d
        if risk >= RiskLevel.HIGH and self.config.local_only and self._uses_network(action, args):
            d = Decision(False, "Blocked: local-only mode forbids network access", risk=risk)
            self.journal.record(action, risk, args, "denied", d.reason)
            return d
        if action == "run_shell" and not self.config.shell_enabled:
            d = Decision(False, "Shell execution is disabled in settings", risk=risk)
            self.journal.record(action, risk, args, "denied", d.reason)
            return d

        needs = self.config.require_confirmation and risk >= RiskLevel.HIGH
        if action in allowed or base in allowed or action in self._session_approvals:
            needs = False
        if self.dry_run:
            d = Decision(True, "DRY RUN — no changes were made", needs_confirmation=False,
                         risk=risk, dry_run=True)
            self.journal.record(action, risk, args, "dry_run", d.reason)
            return d
        d = Decision(True, "allowed", needs_confirmation=needs, risk=risk)
        return d

    def authorize(self, action: str, risk: RiskLevel,
                  args: Mapping[str, Any] | None = None) -> Decision:
        """evaluate() + ask the user when confirmation is required."""
        decision = self.evaluate(action, risk, args)
        args = dict(args or {})
        if not decision.allowed or not decision.needs_confirmation:
            if not decision.needs_confirmation:
                self.journal.record(action, RiskLevel.parse(risk), args,
                                    "allowed" if decision.allowed else "denied", decision.reason)
            return decision
        approved = False
        if self.confirm_callback:
            try:
                approved = bool(self.confirm_callback(action, decision.risk, args))
            except Exception as exc:
                log.warning("Confirmation callback failed: %s", exc)
                approved = False
        if approved:
            with self._lock:
                self._session_approvals.add(action)
            d = Decision(True, "approved by user", risk=decision.risk)
            self.journal.record(action, decision.risk, args, "approved", d.reason)
            return d
        d = Decision(False, "declined by user", risk=decision.risk)
        self.journal.record(action, decision.risk, args, "declined", d.reason)
        return d

    def report_result(self, action: str, risk: RiskLevel, args: Mapping[str, Any], result: Any) -> None:
        self.journal.record(action, RiskLevel.parse(risk), args, "executed", "completed", str(result))

    def approve_for_session(self, action: str) -> None:
        with self._lock:
            self._session_approvals.add(action)

    def revoke(self, action: str) -> None:
        with self._lock:
            self._session_approvals.discard(action)

    @staticmethod
    def _uses_network(action: str, args: Mapping[str, Any]) -> bool:
        network_tools = {"web_search", "read_webpage", "deep_web_research", "exa_search",
                         "youtube_info", "open_url", "weather", "news", "currency"}
        return action in network_tools or any(k in args for k in ("url", "urls"))


class UndoManager:
    """Reversible file operations. Deletes are moved to a trash folder first."""

    def __init__(self, config: NixiConfig | None = None, journal: ActionJournal | None = None):
        self.config = config or get_config()
        self.journal = journal if journal is not None else ActionJournal(enabled=self.config.audit_enabled)
        self.trash = Path(self.config.data_dir) / "trash"

    def record_move(self, src: str | Path, dst: str | Path) -> int:
        return self.journal.add_undo("move", {"src": str(src), "dst": str(dst)})

    def record_delete(self, original: str | Path, trash_path: str | Path) -> int:
        return self.journal.add_undo("delete", {"src": str(original), "trash": str(trash_path)})

    def undo_last(self) -> str:
        entries = self.journal.pending_undo()
        if not entries:
            return "Nothing to undo."
        entry = entries[0]
        try:
            payload = json.loads(entry["payload"])
            if entry["op"] == "move":
                src, dst = Path(payload["src"]), Path(payload["dst"])
                if dst.exists() and not src.exists():
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(src))
            elif entry["op"] == "delete":
                src, trash = Path(payload["src"]), Path(payload["trash"])
                if trash.exists():
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(trash), str(src))
            else:
                return f"Unknown undo operation: {entry['op']}"
            self.journal.mark_undone(int(entry["id"]))
            return f"Undid {entry['op']}: {payload.get('src')}"
        except (OSError, ValueError, KeyError) as exc:
            return f"Undo failed: {exc}"

    def safe_delete(self, path: str | Path) -> str:
        p = Path(path)
        if not p.exists():
            return f"Not found: {p}"
        self.trash.mkdir(parents=True, exist_ok=True)
        target = self.trash / f"{uuid.uuid4().hex[:8]}_{p.name}"
        try:
            shutil.move(str(p), str(target))
            self.record_delete(p, target)
            return f"Moved to trash (undoable): {p.name}"
        except OSError as exc:
            return f"Could not trash {p.name}: {exc}"

    def safe_move(self, src: str | Path, dst: str | Path) -> str:
        s, d = Path(src), Path(dst)
        if not s.exists():
            return f"Not found: {s}"
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            if d.exists():
                d = d.with_name(f"{d.stem}_{uuid.uuid4().hex[:6]}{d.suffix}")
            shutil.move(str(s), str(d))
            self.record_move(s, d)
            return f"Moved {s.name} -> {d}"
        except OSError as exc:
            return f"Could not move {s.name}: {exc}"


def safe_move(src: str | Path, dst: str | Path, manager: UndoManager | None = None) -> str:
    return (manager or UndoManager()).safe_move(src, dst)


def safe_delete(path: str | Path, manager: UndoManager | None = None) -> str:
    return (manager or UndoManager()).safe_delete(path)
