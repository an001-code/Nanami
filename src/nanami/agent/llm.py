"""LLM Provider 抽象：统一 OpenAI 兼容协议，支持多服务商可切换。"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from ..config import resolve_api_key


def build_llm(
    cfg: dict[str, Any],
    *,
    vision: bool = False,
    temperature: float | None = None,
) -> BaseChatModel:
    """根据配置构建 Chat 模型。vision=True 时使用视觉模型；temperature 覆盖配置值。"""
    llm_cfg = cfg["llm"]
    provider_name = llm_cfg["provider"]
    provider = llm_cfg["providers"][provider_name]

    model = llm_cfg.get("vision_model") if vision else llm_cfg.get("model")

    return ChatOpenAI(
        model=model,
        base_url=provider["base_url"],
        api_key=resolve_api_key(provider),
        temperature=(
            temperature if temperature is not None else llm_cfg.get("temperature", 0.7)
        ),
    )
