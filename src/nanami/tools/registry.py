"""工具注册表：组装内置工具（MCP 工具在 Phase 2 接入）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool

from ..config import PROJECT_ROOT
from .builtin.file_ops import make_file_tools
from .builtin.web_search import web_search


def build_tools(cfg: dict[str, Any]) -> list[BaseTool]:
    tools: list[BaseTool] = [web_search]

    workspace = cfg.get("workspace", {}).get("root", "workspace")
    workspace_path = Path(workspace)
    if not workspace_path.is_absolute():
        workspace_path = PROJECT_ROOT / workspace
    tools.extend(make_file_tools(workspace_path))

    return tools
