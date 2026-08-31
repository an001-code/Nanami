"""记忆相关的 LLM 操作：对话摘要、滚动压缩、画像提取。"""
from __future__ import annotations

import json
import logging
import re
from typing import Callable

from langchain_core.language_models.chat_models import BaseChatModel

from .profile import ProfileUpdate

logger = logging.getLogger(__name__)


class MemorySummarizer:
    def __init__(self, llm: BaseChatModel, name_getter: Callable[[], str] | None = None) -> None:
        self._llm = llm
        self._name_getter = name_getter or (lambda: "七海")
        self._profile_llm = None
        try:
            self._profile_llm = llm.with_structured_output(ProfileUpdate, method="json_mode")
        except Exception as e:  # noqa: BLE001 - json_mode 不可用则走容错解析
            logger.warning("画像结构化输出初始化失败，将用容错 JSON 解析：%s", e)

    def summarize_turn(self, user_text: str, reply_text: str) -> str:
        name = self._name_getter()
        prompt = (
            f"请用一句中文概括下面这轮对话的核心内容（用户说了什么、{name}回应了什么，"
            "以及涉及的事实、偏好或决定），只输出这一句概括，不要加任何前缀或解释：\n\n"
            f"用户：{user_text}\n{name}：{reply_text}"
        )
        try:
            resp = self._llm.invoke(prompt)
            text = self._as_text(resp).strip()
            return text or user_text
        except Exception as e:  # noqa: BLE001
            logger.warning("本轮摘要失败：%s", e)
            return user_text

    def compress(self, old_summary: str, turns: list[dict]) -> str:
        history_text = "\n".join(
            f"{m.get('role', '?')}: {m.get('content', '')}" for m in turns
        )
        prompt = (
            "下面是一段对话历史，以及之前已经总结过的摘要。"
            "请把两者合并成一份新的、简洁的滚动摘要，保留关键事实、用户偏好、话题和决定，"
            "省略寒暄和冗余细节。只输出摘要本身，不要加前缀。\n\n"
            f"[已有摘要]\n{old_summary or '（无）'}\n\n[新增对话]\n{history_text}"
        )
        try:
            resp = self._llm.invoke(prompt)
            text = self._as_text(resp).strip()
            return text or old_summary
        except Exception as e:  # noqa: BLE001
            logger.warning("压缩摘要失败：%s", e)
            return old_summary

    def extract_profile(self, user_text: str, reply_text: str) -> ProfileUpdate | None:
        prompt = self._profile_prompt(user_text, reply_text)
        if self._profile_llm is not None:
            try:
                result = self._profile_llm.invoke(prompt)
                if isinstance(result, ProfileUpdate):
                    return result
            except Exception as e:  # noqa: BLE001
                logger.warning("画像提取（json_mode）失败，尝试容错解析：%s", e)
        return self._fallback_extract(prompt)

    def _fallback_extract(self, prompt: str) -> ProfileUpdate | None:
        try:
            resp = self._llm.invoke(prompt)
            data = self._parse_json(self._as_text(resp))
            if not data:
                return None
            return ProfileUpdate(
                name=data.get("name"),
                preferences=data.get("preferences") or [],
                impressions=data.get("impressions") or [],
                facts=data.get("facts") or [],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("画像提取兜底失败：%s", e)
            return None

    def _profile_prompt(self, user_text: str, reply_text: str) -> str:
        name = self._name_getter()
        return (
            "请从下面这轮对话中提取用户的信息，输出 JSON 对象，字段："
            "name（用户名字，没有则 null）、preferences（偏好列表）、"
            "impressions（你对用户性格/印象的判断列表）、facts（用户提到的事实列表）。"
            "没有的字段给空列表。只输出 JSON，不要加任何其他内容。\n\n"
            f"用户：{user_text}\n{name}：{reply_text}"
        )

    @staticmethod
    def _as_text(resp: object) -> str:
        if hasattr(resp, "content"):
            return resp.content or ""  # type: ignore[return-value]
        return str(resp)

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        text = text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            return None
