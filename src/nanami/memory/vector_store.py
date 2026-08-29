"""语义记忆：chromadb 持久化 + 向量检索（只存摘要，线程安全）。"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import chromadb

from .embedder import EmbeddingError, QwenEmbedder


class VectorStore:
    def __init__(
        self,
        persist_dir: str | Path,
        embedder: QwenEmbedder,
        collection_name: str = "conversation_summaries",
    ) -> None:
        path = Path(persist_dir)
        path.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        self._client = chromadb.PersistentClient(path=str(path))
        self._col = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._lock = threading.Lock()

    def add(self, item_id: str, text: str, metadata: dict[str, Any]) -> None:
        emb = self._embedder.embed_texts([text])
        with self._lock:
            self._col.add(
                ids=[item_id],
                embeddings=emb,
                documents=[text],
                metadatas=[metadata],
            )

    def search(
        self,
        query: str,
        n_results: int = 5,
        max_distance: float = 0.5,
    ) -> list[dict]:
        try:
            emb = self._embedder.embed_query(query)
        except EmbeddingError:
            return []
        with self._lock:
            res = self._col.query(
                query_embeddings=[emb],
                n_results=n_results,
                include=["documents", "distances", "metadatas"],
            )
        docs = res.get("documents") or [[]]
        dists = res.get("distances") or [[]]
        metas = res.get("metadatas") or [[]]
        hits: list[dict] = []
        for doc, dist, meta in zip(docs[0], dists[0], metas[0]):
            if dist is not None and dist <= max_distance:
                hits.append({"text": doc, "distance": dist, "metadata": meta or {}})
        return hits

    def list_all(self, limit: int = 100) -> list[dict]:
        """列出集合中全部文档（含 metadata），不请求 embedding。"""
        with self._lock:
            res = self._col.get(limit=limit, include=["documents", "metadatas"])
        ids = res.get("ids") or []
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        return [
            {"id": i, "text": doc, "metadata": meta or {}}
            for i, doc, meta in zip(ids, docs, metas)
        ]

    def count(self) -> int:
        with self._lock:
            return self._col.count()
