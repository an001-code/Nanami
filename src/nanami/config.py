"""配置加载：读取 config/config.yaml 并从环境变量注入 API key。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """加载 YAML 配置。path 为空时使用项目默认 config/config.yaml。"""
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_pet_name(cfg: dict[str, Any]) -> str:
    """读取桌宠显示名，缺省「七海」。"""
    return (cfg.get("pet") or {}).get("name") or "七海"


def resolve_api_key(provider: dict[str, Any]) -> str:
    """从 provider 配置的 api_key_env 指定的环境变量读取 key。本地服务无 key。"""
    env = provider.get("api_key_env", "")
    if env:
        key = os.environ.get(env, "")
        if key:
            return key
        raise ValueError(f"缺少 API key：请设置环境变量 {env}")
    return "not-needed"  # 本地服务（如 ollama）无需真实 key


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    """写回 YAML 配置。注意：safe_dump 会丢弃原文件中的注释。

    path 为空时使用默认 config/config.yaml。如需保留注释可后续换 ruamel.yaml。
    """
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
