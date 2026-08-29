"""联网搜索工具。"""
from __future__ import annotations

from pydantic import BaseModel, Field
from langchain_core.tools import tool


class WebSearchInput(BaseModel):
    query: str = Field(description="搜索关键词")


@tool("web_search", args_schema=WebSearchInput)
def web_search(query: str) -> str:
    """联网搜索，返回若干条结果摘要。"""
    try:
        from ddgs import DDGS
    except ImportError:
        return "联网搜索未安装依赖，请先 `pip install ddgs`。"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
    except Exception as e:  # noqa: BLE001 - 网络/服务异常
        return f"搜索失败：{e}"

    if not results:
        return "未找到相关结果。"
    lines = []
    for r in results:
        title = r.get("title", "")
        body = (r.get("body") or "")[:150]
        href = r.get("href", "")
        lines.append(f"- {title}\n  {body}\n  {href}")
    return "\n".join(lines)
