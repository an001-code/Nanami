"""NanamiAgent：封装 llm / tools / graph / memory，提供同步 chat 接口。"""
from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from ..memory.manager import MemoryManager
from ..permissions.policy import PermissionPolicy
from .graph import build_graph
from .llm import build_llm
from .prompts import build_system_prompt

VALID_EMOTIONS = {
    "neutral", "happy", "excited", "sad", "angry", "surprised", "shy",
    "confused", "tired", "concerned", "affectionate", "curious", "calm",
    "anxiety",
}

# 中文情绪词 → 英文情绪名：模型有时会偷懒输出中文，做一层映射兜底
_EMOTION_ALIASES = {
    "中性": "neutral", "平常": "neutral", "平静": "calm", "冷静": "calm",
    "开心": "happy", "高兴": "happy", "快乐": "happy", "愉快": "happy",
    "兴奋": "excited", "激动": "excited",
    "难过": "sad", "伤心": "sad", "悲伤": "sad", "沮丧": "sad", "失落": "sad",
    "生气": "angry", "愤怒": "angry", "恼火": "angry",
    "惊讶": "surprised", "吃惊": "surprised", "惊喜": "surprised",
    "害羞": "shy", "羞涩": "shy",
    "困惑": "confused", "疑惑": "confused", "不解": "confused",
    "疲惫": "tired", "累": "tired",
    "担心": "concerned", "担忧": "concerned", "关切": "concerned",
    "亲昵": "affectionate", "温柔": "affectionate", "喜爱": "affectionate",
    "好奇": "curious",
    "焦虑": "anxiety", "不安": "anxiety",
}

# 带 emotion: 前缀的标签（半角/全角冒号、冒号前后可带空格）
_EMOTION_TAG = re.compile(
    r"【\s*emotion\s*[:：]\s*([a-zA-Z一-鿿]+)\s*】"
)
# 裸标签：只包情绪词本身，如 【happy】 / 【开心】
_BARE_TAG = re.compile(r"【\s*([a-zA-Z一-鿿]+)\s*】")


def _resolve_emotion(raw: str) -> str | None:
    """把情绪词（英文或中文）解析成英文情绪名；无法识别返回 None。"""
    name = raw.strip()
    low = name.lower()
    if low in VALID_EMOTIONS:
        return low
    return _EMOTION_ALIASES.get(name)


def parse_emotion(text: str) -> tuple[str, str]:
    """从回复文本中解析情绪标签，返回 (纯文本, 情绪)。

    模型可能输出多种形态：`【emotion:happy】`、`【emotion：开心】`、
    `【开心】` 等，这里统一识别并从正文中剥离，避免情绪词泄漏到用户看到的文字里。
    """
    # 1) 带 emotion: 前缀的规范标签
    match = _EMOTION_TAG.search(text)
    if match:
        emotion = _resolve_emotion(match.group(1)) or "neutral"
        return _EMOTION_TAG.sub("", text).strip(), emotion

    # 2) 末尾裸标签（仅当能明确识别为情绪词时才剥离，避免误删正文）
    stripped = text.rstrip()
    match = _BARE_TAG.search(stripped)
    if match and match.end() == len(stripped):
        emotion = _resolve_emotion(match.group(1))
        if emotion is not None:
            return stripped[: match.start()].strip(), emotion

    return text.strip(), "neutral"


def recent_to_messages(recent: list[dict]) -> list:
    """把工作记忆的 recent（[{role, content}]）转成 LangChain 消息。"""
    msgs = []
    for m in recent:
        content = m.get("content", "")
        if m.get("role") == "assistant":
            msgs.append(AIMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    return msgs


class NanamiAgent:
    def __init__(
        self,
        cfg: dict[str, Any],
        tools: list[Any],
        memory: MemoryManager,
        policy: PermissionPolicy,
    ) -> None:
        self.cfg = cfg
        self.memory = memory
        self.policy = policy
        self.llm = build_llm(cfg)
        self.graph = build_graph(self.llm, tools, policy=policy)
        self.memory.start()

    def chat(self, text: str, thread_id: str = "default") -> tuple[str, str]:
        """返回 (回复文本, 情绪)。"""
        profile_text = self.memory.build_profile_text()
        memories_text = self.memory.build_memories_text(text)
        summary, recent = self.memory.load_work_memory()

        system = build_system_prompt(profile_text, memories_text)
        messages: list = []
        if summary:
            messages.append(HumanMessage(content=f"[之前的对话摘要]\n{summary}"))
        messages += recent_to_messages(recent)
        messages.append(HumanMessage(content=text))

        result = self.graph.invoke(
            {"messages": messages, "system": system},
            config={"configurable": {"thread_id": thread_id}},
        )
        last = result["messages"][-1]
        reply = last.content if hasattr(last, "content") else str(last)
        reply, emotion = parse_emotion(reply)

        self.memory.append_history(thread_id, text, reply)
        self.memory.enqueue_turn(thread_id, text, reply)
        return reply, emotion

    def close(self) -> None:
        self.memory.stop()
