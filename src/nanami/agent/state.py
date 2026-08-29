"""LangGraph 状态定义。"""
from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    # 系统提示词，每次 invoke 时由调用方传入（可动态注入记忆）
    system: str
