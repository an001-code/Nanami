"""Qwen embedding 客户端：把中文文本转成向量（经 DashScope OpenAI 兼容端点）。"""
from __future__ import annotations

from openai import OpenAI


class EmbeddingError(Exception):
    """embedding 调用失败。"""


class QwenEmbedder:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "text-embedding-v3",
        dimensions: int | None = None,
        batch_size: int = 16,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._dimensions = dimensions
        self._batch_size = max(1, batch_size)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            kwargs: dict = {"model": self._model, "input": batch}
            if self._dimensions is not None:
                kwargs["dimensions"] = self._dimensions
            try:
                resp = self._client.embeddings.create(**kwargs)
            except Exception as e:  # noqa: BLE001 - 统一包装成 EmbeddingError
                raise EmbeddingError(f"embedding 调用失败：{e}") from e
            items = sorted(resp.data, key=lambda d: d.index)
            out.extend([d.embedding for d in items])
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
