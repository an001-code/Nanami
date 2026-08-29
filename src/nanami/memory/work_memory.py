"""工作记忆：滚动摘要 + 最近 N 轮原文，双阈值压缩，存 Redis。"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)


class WorkMemory:
    def __init__(
        self,
        redis_client: Any,
        key_prefix: str = "nanami:",
        high_token_threshold: int = 4000,
        low_token_threshold: int = 2000,
        keep_recent_turns: int = 6,
    ) -> None:
        self._redis = redis_client
        self._summary_key = f"{key_prefix}summary"
        self._recent_key = f"{key_prefix}recent"
        self._high = high_token_threshold
        self._low = low_token_threshold
        self._keep_turns = max(1, keep_recent_turns)
        self._lock = threading.Lock()
        try:
            import tiktoken

            self._enc = tiktoken.get_encoding("cl100k_base")
        except Exception:  # noqa: BLE001 - tokenizer 不可用时退化为字符估算
            self._enc = None

    def _count_tokens(self, text: str) -> int:
        if self._enc is None:
            return len(text)
        try:
            return len(self._enc.encode(text))
        except Exception:  # noqa: BLE001
            return len(text)

    @staticmethod
    def _recent_to_text(recent: list[dict]) -> str:
        return "\n".join(f"{m.get('role', '?')}: {m.get('content', '')}" for m in recent)

    def load(self) -> tuple[str, list[dict]]:
        try:
            summary = self._redis.get(self._summary_key) or ""
            raw_recent = self._redis.get(self._recent_key) or "[]"
            recent = json.loads(raw_recent)
        except Exception as e:  # noqa: BLE001
            logger.warning("加载工作记忆失败：%s", e)
            return "", []
        return summary, recent

    def ping(self) -> bool:
        try:
            return bool(self._redis.ping())
        except Exception:  # noqa: BLE001
            return False

    def append_turn(self, user_text: str, reply_text: str) -> None:
        with self._lock:
            _, recent = self.load()
            recent.append({"role": "user", "content": user_text})
            recent.append({"role": "assistant", "content": reply_text})
            self._save_recent(recent)

    def maybe_compress(self, compress_fn: Callable[[str, list[dict]], str]) -> str | None:
        with self._lock:
            summary, recent = self.load()
            if self._count_tokens(self._recent_to_text(recent)) <= self._high:
                return None
            keep = list(recent)
            min_msgs = self._keep_turns * 2  # 每轮 user+assistant 两条
            while (
                self._count_tokens(self._recent_to_text(keep)) > self._low
                and len(keep) > min_msgs
            ):
                keep = keep[2:]  # 折叠最老的一轮
            to_summarize = recent[: len(recent) - len(keep)]
            if not to_summarize:
                return None
            try:
                new_summary = compress_fn(summary, to_summarize)
            except Exception as e:  # noqa: BLE001
                logger.warning("压缩摘要失败：%s", e)
                return None
            if new_summary:
                try:
                    self._redis.set(self._summary_key, new_summary)
                except Exception as e:  # noqa: BLE001
                    logger.warning("保存摘要失败：%s", e)
            self._save_recent(keep)
            return new_summary

    def _save_recent(self, recent: list[dict]) -> None:
        try:
            self._redis.set(
                self._recent_key, json.dumps(recent, ensure_ascii=False)
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("保存 recent 失败：%s", e)
