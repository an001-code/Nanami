"""工作区文件读写工具。所有路径被限制在 workspace 根目录内。"""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field


class ListFilesInput(BaseModel):
    path: str = Field(default="", description="相对工作区根目录的子路径，空串表示根目录")


class ReadFileInput(BaseModel):
    path: str = Field(description="相对工作区根目录的文件路径")


class WriteFileInput(BaseModel):
    path: str = Field(description="相对工作区根目录的文件路径")
    content: str = Field(description="要写入的文件内容")


def make_file_tools(workspace_root: str | Path) -> list[BaseTool]:
    root = Path(workspace_root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    def _resolve(path: str) -> Path:
        p = (root / path).resolve()
        if p != root and root not in p.parents:
            raise ValueError(f"路径越界：{path} 不在工作区 {root} 内")
        return p

    @tool("list_files", args_schema=ListFilesInput)
    def list_files(path: str = "") -> str:
        """列出工作区目录下的文件与子目录。"""
        try:
            target = _resolve(path)
        except ValueError as e:
            return str(e)
        if not target.is_dir():
            return f"不是目录：{path}"
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
        if not entries:
            return f"目录为空：{path or '.'}"
        lines = []
        for e in entries:
            kind = "DIR " if e.is_dir() else "FILE"
            lines.append(f"{kind}  {e.name}")
        return "\n".join(lines)

    @tool("read_file", args_schema=ReadFileInput)
    def read_file(path: str) -> str:
        """读取工作区内某个文件的内容。"""
        try:
            target = _resolve(path)
            return target.read_text(encoding="utf-8")
        except ValueError as e:
            return str(e)
        except (FileNotFoundError, IsADirectoryError) as e:
            return f"无法读取：{e}"
        except UnicodeDecodeError:
            return "该文件不是文本文件，无法读取。"

    @tool("write_file", args_schema=WriteFileInput)
    def write_file(path: str, content: str) -> str:
        """在工作区内写入文件，自动创建父目录。"""
        try:
            target = _resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return f"已写入：{target}"
        except ValueError as e:
            return str(e)
        except OSError as e:
            return f"写入失败：{e}"

    return [list_files, read_file, write_file]
