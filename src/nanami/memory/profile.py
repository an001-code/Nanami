"""用户画像：结构化存储（Redis）+ 增量合并。"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProfileUpdate(BaseModel):
    name: str | None = None
    preferences: list[str] = []
    impressions: list[str] = []
    facts: list[str] = []


class ProfileStore:
    def __init__(self, redis_client: Any, key: str = "nanami:profile") -> None:
        self._redis = redis_client
        self._key = key

    def load(self) -> dict:
        try:
            raw = self._redis.get(self._key)
        except Exception as e:  # noqa: BLE001
            logger.warning("读取画像失败：%s", e)
            return {}
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            logger.warning("画像 JSON 损坏，重置为空")
            return {}

    def save(self, profile: dict) -> None:
        try:
            self._redis.set(self._key, json.dumps(profile, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            logger.warning("保存画像失败：%s", e)


class ProfileManager:
    def __init__(self, store: ProfileStore) -> None:
        self._store = store
        self._lock = threading.Lock()
        self._cache: dict | None = None

    def get(self) -> dict:
        if self._cache is None:
            with self._lock:
                if self._cache is None:
                    self._cache = self._store.load()
        return self._cache

    def apply_update(self, update: ProfileUpdate) -> dict:
        with self._lock:
            profile = self._cache if self._cache is not None else self._store.load()
            if update.name:
                profile["name"] = update.name
            profile.setdefault("preferences", [])
            profile.setdefault("impressions", [])
            profile.setdefault("facts", [])
            profile["preferences"] = self._merge(profile["preferences"], update.preferences)
            profile["impressions"] = self._merge(profile["impressions"], update.impressions)
            profile["facts"] = self._merge(profile["facts"], update.facts)
            profile["updated_at"] = self._now()
            self._store.save(profile)
            self._cache = profile
            return profile

    def add_fact(self, content: str) -> dict:
        with self._lock:
            profile = self._cache if self._cache is not None else self._store.load()
            profile.setdefault("facts", [])
            if content not in profile["facts"]:
                profile["facts"].append(content)
            profile["updated_at"] = self._now()
            self._store.save(profile)
            self._cache = profile
            return profile

    def to_text(self) -> str:
        profile = self.get()
        if not profile:
            return ""
        lines: list[str] = []
        if profile.get("name"):
            lines.append(f"名字：{profile['name']}")
        for key, label in [
            ("preferences", "偏好"),
            ("impressions", "印象"),
            ("facts", "事实"),
        ]:
            items = profile.get(key) or []
            if items:
                lines.append(f"{label}：" + "；".join(items))
        return "\n".join(lines)

    @staticmethod
    def _merge(existing: list, new: list) -> list:
        for item in new:
            if item and item not in existing:
                existing.append(item)
        return existing

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")
