"""RAG-lite knowledge base — FTS5 when available, LIKE fallback, PII-safe."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from nixi.config import NixiConfig, get_config
from nixi.privacy.vision_guard import redact_pii
from nixi.logging_utils import get_logger

log = get_logger("knowledge")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def _has_fts5() -> bool:
    try:
        c = sqlite3.connect(":memory:")
        c.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        c.close()
        return True
    except Exception:
        return False

HAS_FTS5 = _has_fts5()


class KnowledgeStore:
    def __init__(self, config: NixiConfig | None = None, db_path: str | Path | None = None):
        self.config = config or get_config()
        self.db_path = str(db_path or self.config.data_path("knowledge.db"))
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE, mtime REAL, indexed_at REAL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER, chunk_index INTEGER, text TEXT,
                FOREIGN KEY(doc_id) REFERENCES documents(id) ON DELETE CASCADE)""")
            if HAS_FTS5:
                conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='id')")
                conn.execute("""CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text); END""")
                conn.execute("""CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text); END""")
            conn.commit()

    def _chunk_text(self, text: str) -> list[str]:
        if len(text) <= CHUNK_SIZE:
            return [text] if text.strip() else []
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            # try to break at paragraph boundary
            if end < len(text):
                nl = text.rfind("\n\n", start, end)
                if nl > start + CHUNK_SIZE // 2:
                    end = nl
            chunks.append(text[start:end].strip())
            if end >= len(text):
                break
            start = end - CHUNK_OVERLAP
        return [c for c in chunks if c]

    def index_file(self, path: str | Path) -> int:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return 0
        if p.suffix.lower() not in tuple(s.lower() for s in self.config.knowledge_extensions):
            return 0
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0
        text = text.strip()
        if not text:
            return 0
        mtime = p.stat().st_mtime
        with self._connect() as conn:
            # skip if unchanged
            row = conn.execute("SELECT id, mtime FROM documents WHERE path=?", (str(p),)).fetchone()
            if row and row["mtime"] == mtime:
                return 0
            if row:
                conn.execute("DELETE FROM chunks WHERE doc_id=?", (row["id"],))
                conn.execute("DELETE FROM documents WHERE id=?", (row["id"],))
            cur = conn.execute("INSERT INTO documents (path, mtime, indexed_at) VALUES (?,?,?)",
                               (str(p), mtime, time.time()))
            doc_id = cur.lastrowid
            chunks = self._chunk_text(text)
            for idx, chunk in enumerate(chunks):
                conn.execute("INSERT INTO chunks (doc_id, chunk_index, text) VALUES (?,?,?)",
                             (doc_id, idx, chunk))
            conn.commit()
            return len(chunks)

    def index_dirs(self) -> dict[str, Any]:
        total_files = 0
        total_chunks = 0
        for d in self.config.knowledge_dirs:
            root = Path(d).expanduser()
            if not root.exists():
                continue
            for ext in self.config.knowledge_extensions:
                for f in root.rglob(f"*{ext}"):
                    if f.is_file():
                        n = self.index_file(f)
                        if n:
                            total_files += 1
                            total_chunks += n
        return {"files": total_files, "chunks": total_chunks}

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        with self._connect() as conn:
            if HAS_FTS5:
                try:
                    # FTS5 query — escape special chars
                    safe_q = query.replace('"', '""')
                    rows = conn.execute("""
                        SELECT c.text as text, d.path as path, rank
                        FROM chunks_fts
                        JOIN chunks c ON c.id = chunks_fts.rowid
                        JOIN documents d ON d.id = c.doc_id
                        WHERE chunks_fts MATCH ?
                        ORDER BY rank LIMIT ?
                    """, (safe_q, limit)).fetchall()
                    if rows:
                        return [{"text": redact_pii(r["text"][:800]), "path": r["path"], "score": r["rank"]} for r in rows]
                except sqlite3.OperationalError:
                    pass
            # LIKE fallback
            like = f"%{query}%"
            rows = conn.execute("""
                SELECT c.text as text, d.path as path FROM chunks c
                JOIN documents d ON d.id=c.doc_id WHERE c.text LIKE ? LIMIT ?
            """, (like, limit)).fetchall()
            return [{"text": redact_pii(r["text"][:800]), "path": r["path"], "score": 0} for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            docs = conn.execute("SELECT COUNT(*) as n FROM documents").fetchone()["n"]
            chunks = conn.execute("SELECT COUNT(*) as n FROM chunks").fetchone()["n"]
            return {"documents": docs, "chunks": chunks, "fts5": HAS_FTS5}
