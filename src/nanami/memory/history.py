"""完整对话历史：PostgreSQL 自建表，同步存档（供用户查看历史）。"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConversationHistory:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._available = False
        try:
            self._init()
            self._available = True
        except Exception as e:  # noqa: BLE001 - PG 不可用时降级，不阻塞启动
            logger.warning("PostgreSQL 不可用，完整历史存档将跳过：%s", e)

    def _connect(self) -> Any:
        import psycopg

        return psycopg.connect(self._dsn)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            conn.commit()

    def append(self, thread_id: str, role: str, content: str) -> None:
        if not self._available:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO messages (thread_id, role, content) VALUES (%s, %s, %s)",
                    (thread_id, role, content),
                )
                conn.commit()
        except Exception as e:  # noqa: BLE001 - 存档失败不影响对话
            logger.warning("历史存档失败：%s", e)

    def list(
        self, thread_id: str, limit: int = 100, before_id: int | None = None
    ) -> list[dict]:
        if not self._available:
            return []
        with self._connect() as conn:
            if before_id is not None:
                rows = conn.execute(
                    "SELECT id, thread_id, role, content, created_at FROM messages "
                    "WHERE thread_id = %s AND id < %s ORDER BY id DESC LIMIT %s",
                    (thread_id, before_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, thread_id, role, content, created_at FROM messages "
                    "WHERE thread_id = %s ORDER BY id DESC LIMIT %s",
                    (thread_id, limit),
                ).fetchall()
        return [
            {
                "id": r[0],
                "thread_id": r[1],
                "role": r[2],
                "content": r[3],
                "created_at": r[4].isoformat() if r[4] is not None else None,
            }
            for r in rows
        ]

    def is_available(self) -> bool:
        return self._available

    def count(self, thread_id: str = "default") -> int:
        if not self._available:
            return 0
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE thread_id = %s", (thread_id,)
            ).fetchone()
        return int(row[0]) if row else 0

    def list_threads(self) -> list[dict]:
        if not self._available:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT thread_id, COUNT(*) AS n, MAX(created_at) AS last "
                "FROM messages GROUP BY thread_id ORDER BY last DESC NULLS LAST"
            ).fetchall()
        return [
            {
                "thread_id": r[0],
                "count": r[1],
                "last": r[2].isoformat() if r[2] is not None else None,
            }
            for r in rows
        ]
