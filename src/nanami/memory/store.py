"""长期记忆存储：sqlite 基础版。"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
                """
            )

    def add(self, content: str, category: str = "general") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO memories (content, category) VALUES (?, ?)",
                (content, category),
            )
            return cur.lastrowid

    def search(self, query: str, limit: int = 5) -> list[dict]:
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, content, category, created_at FROM memories "
                "WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (like, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def all(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, content, category, created_at FROM memories "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
