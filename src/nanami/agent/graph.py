"""LangGraph ReAct 风格 agent 核心：输入 → LLM 决策(绑定工具) → 权限检查 → 执行 → 循环。"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from ..permissions.policy import PermissionPolicy
from .state import AgentState


def build_graph(
    llm: BaseChatModel,
    tools: list[Any],
    policy: PermissionPolicy | None = None,
) -> Any:
    """构建并编译 agent graph。历史由调用方显式传入 messages，无需 checkpointer。"""
    policy = policy or PermissionPolicy(default="deny")
    tools_by_name = {t.name: t for t in tools}

    def call_model(state: AgentState) -> dict:
        messages = [SystemMessage(content=state.get("system", ""))] + state["messages"]
        model = llm.bind_tools(tools) if tools else llm
        response = model.invoke(messages)
        return {"messages": [response]}

    def _execute_tool_call(tc: dict) -> str:
        name = tc["name"]
        tool = tools_by_name.get(name)
        if tool is None:
            return f"未知工具：{name}"
        if policy.check(name, tc.get("args", {})) == "deny":
            return f"操作「{name}」需要你的授权，已被取消。"
        try:
            return str(tool.invoke(tc.get("args", {})))
        except Exception as e:  # noqa: BLE001 - 工具异常需回传给模型
            return f"工具「{name}」执行出错：{e}"

    def run_tools(state: AgentState) -> dict:
        last = state["messages"][-1]
        results = [
            ToolMessage(content=_execute_tool_call(tc), tool_call_id=tc["id"])
            for tc in last.tool_calls
        ]
        return {"messages": results}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    if tools:
        workflow.add_node("tools", run_tools)
        workflow.add_conditional_edges(
            "agent", should_continue, {"tools": "tools", END: END}
        )
        workflow.add_edge("tools", "agent")
    else:
        workflow.add_edge("agent", END)

    workflow.add_edge(START, "agent")
    return workflow.compile()
