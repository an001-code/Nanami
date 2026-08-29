"""记忆编排门面：协调语义记忆 / 工作记忆 / 画像 / 历史与后台队列。"""
from __future__ import annotations

import logging
import queue
import uuid
from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .history import ConversationHistory
from .profile import ProfileManager
from .summarizer import MemorySummarizer
from .vector_store import VectorStore
from .worker import MemoryWorker, TurnRecord
from .work_memory import WorkMemory

logger = logging.getLogger(__name__)


class RememberInput(BaseModel):
    content: str = Field(description="要记住的内容，例如用户偏好、习惯、重要事实")
    category: str = Field(default="general", description="记忆分类（保留兼容，暂不使用）")


class MemoryManager:
    def __init__(
        self,
        cfg: dict[str, Any],
        vector_store: VectorStore,
        work_memory: WorkMemory,
        profile_manager: ProfileManager,
        summarizer: MemorySummarizer,
        history: ConversationHistory,
    ) -> None:
        self._vs = vector_store
        self._wm = work_memory
        self._pm = profile_manager
        self._summarizer = summarizer
        self._history = history

        mem_cfg = cfg.get("memory", {})
        worker_cfg = mem_cfg.get("worker", {})
        self._queue: queue.Queue[TurnRecord | None] = queue.Queue(
            maxsize=worker_cfg.get("queue_size", 100)
        )
        self._worker = MemoryWorker(
            self._vs, self._wm, self._summarizer, self._pm, self._queue
        )
        self._shutdown_timeout = worker_cfg.get("shutdown_timeout_sec", 5)

        vector_cfg = mem_cfg.get("vector", {})
        self._top_k = vector_cfg.get("top_k", 5)
        self._max_distance = vector_cfg.get("max_distance", 0.5)

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._worker.stop(timeout=self._shutdown_timeout)

    def build_profile_text(self) -> str:
        return self._pm.to_text()

    def search(self, query: str) -> list[dict]:
        return self._vs.search(
            query, n_results=self._top_k, max_distance=self._max_distance
        )

    def build_memories_text(self, query: str) -> str:
        hits = self.search(query)
        if not hits:
            return ""
        return "\n".join(f"- {h['text']}" for h in hits)

    def load_work_memory(self) -> tuple[str, list[dict]]:
        return self._wm.load()

    def list_semantic(self, limit: int = 100) -> list[dict]:
        return self._vs.list_all(limit)

    def semantic_count(self) -> int:
        return self._vs.count()

    def get_profile(self) -> dict:
        return self._pm.get()

    def list_history(self, thread_id: str = "default", limit: int = 100) -> list[dict]:
        return self._history.list(thread_id, limit)

    def list_threads(self) -> list[dict]:
        return self._history.list_threads()

    def history_count(self, thread_id: str = "default") -> int:
        return self._history.count(thread_id)

    def health(self) -> dict:
        try:
            chroma_ok = self._vs.count() >= 0
        except Exception:  # noqa: BLE001
            chroma_ok = False
        return {
            "postgres": self._history.is_available(),
            "redis": self._wm.ping(),
            "chroma": chroma_ok,
        }

    def append_history(self, thread_id: str, user_text: str, reply_text: str) -> None:
        self._history.append(thread_id, "user", user_text)
        self._history.append(thread_id, "assistant", reply_text)

    def enqueue_turn(self, thread_id: str, user_text: str, reply_text: str) -> None:
        rec = TurnRecord(
            thread_id=thread_id,
            turn_id=uuid.uuid4().hex,
            user_text=user_text,
            reply_text=reply_text,
            ts=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        try:
            self._queue.put_nowait(rec)
        except queue.Full:
            logger.warning("记忆队列已满，丢弃本轮后台处理")

    def make_remember_tool(self) -> BaseTool:
        pm = self._pm

        @tool("remember", args_schema=RememberInput)
        def remember(content: str, category: str = "general") -> str:
            """把重要信息写入用户画像的长期记忆，供以后对话使用。"""
            pm.add_fact(content)
            return f"已记住：{content}"

        return remember
