"""后台异步队列：摘要入库、工作记忆更新/压缩、画像提取。"""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass

from .profile import ProfileManager
from .summarizer import MemorySummarizer
from .vector_store import VectorStore
from .work_memory import WorkMemory

logger = logging.getLogger(__name__)


@dataclass
class TurnRecord:
    thread_id: str
    turn_id: str
    user_text: str
    reply_text: str
    ts: str


class MemoryWorker:
    def __init__(
        self,
        vector_store: VectorStore,
        work_memory: WorkMemory,
        summarizer: MemorySummarizer,
        profile_manager: ProfileManager,
        queue_: "queue.Queue[TurnRecord | None]",
    ) -> None:
        self._vs = vector_store
        self._wm = work_memory
        self._summarizer = summarizer
        self._pm = profile_manager
        self._queue = queue_
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="nanami-memory-worker", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if self._thread is None:
            return
        self._queue.put(None)
        self._thread.join(timeout=timeout)
        self._thread = None

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            try:
                self._process(item)
            except Exception as e:  # noqa: BLE001 - 单条异常不影响后续
                logger.warning("记忆后台处理异常：%s", e)

    def _process(self, item: TurnRecord) -> None:
        # 1. 语义记忆：本轮摘要入向量库
        try:
            summary = self._summarizer.summarize_turn(item.user_text, item.reply_text)
            self._vs.add(
                item.turn_id,
                summary,
                {"thread_id": item.thread_id, "ts": item.ts},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("语义记忆写入失败：%s", e)

        # 2. 工作记忆：更新 recent + 双阈值压缩
        try:
            self._wm.append_turn(item.user_text, item.reply_text)
            self._wm.maybe_compress(self._summarizer.compress)
        except Exception as e:  # noqa: BLE001
            logger.warning("工作记忆更新失败：%s", e)

        # 3. 画像：增量提取合并
        try:
            update = self._summarizer.extract_profile(item.user_text, item.reply_text)
            if update is not None:
                self._pm.apply_update(update)
        except Exception as e:  # noqa: BLE001
            logger.warning("画像更新失败：%s", e)
