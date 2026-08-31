"""仪表盘桥接：QWebChannel 槽，向 JS 暴露记忆只读视图与配置写回。"""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..config import get_pet_name, save_config
from ..memory.manager import MemoryManager
from ..model_importer import ModelImporter
from ..voice.tts import synthesize


class DashboardBridge(QObject):
    model_changed = Signal(str)
    import_finished = Signal(str)
    pet_name_changed = Signal(str)

    def __init__(
        self,
        memory: MemoryManager,
        cfg: dict[str, Any],
        config_path: Path,
        l2d_dir: Path,
        model_importer: ModelImporter,
    ) -> None:
        super().__init__()
        self._memory = memory
        self._cfg = cfg
        self._config_path = config_path
        self._l2d_dir = l2d_dir
        self._model_importer = model_importer

    # ---- 工具 ----
    def _ok(self, data: Any) -> str:
        return json.dumps({"ok": True, "error": None, "data": data}, ensure_ascii=False)

    def _err(self, msg: str) -> str:
        return json.dumps({"ok": False, "error": msg, "data": None}, ensure_ascii=False)

    # ---- 桌宠名称 ----
    @Slot(result=str)
    def getPetName(self) -> str:  # noqa: N802
        return json.dumps({"name": get_pet_name(self._cfg)}, ensure_ascii=False)

    @Slot(str, result=str)
    def savePetName(self, name: str) -> str:  # noqa: N802
        name = name.strip()
        if not name:
            return self._err("名字不能为空")
        self._cfg.setdefault("pet", {})["name"] = name
        try:
            save_config(self._cfg, self._config_path)
        except Exception as e:  # noqa: BLE001
            return self._err(f"写入失败：{e}")
        self.pet_name_changed.emit(name)
        return json.dumps({"ok": True, "error": None}, ensure_ascii=False)

    # ---- 总览 ----
    @Slot(result=str)
    def getOverview(self) -> str:  # noqa: N802
        try:
            health = self._memory.health()
            _, recent = self._memory.load_work_memory()
            profile = self._memory.get_profile()
            counts = {
                "history": self._memory.history_count(),
                "threads": len(self._memory.list_threads()),
                "semantic": self._memory.semantic_count(),
                "work_recent": len(recent),
                "profile_facts": len(profile.get("facts") or []),
            }
            cfg = {
                "provider": self._cfg.get("llm", {}).get("provider"),
                "model": self._cfg.get("llm", {}).get("model"),
                "live2d_model": self._cfg.get("live2d", {}).get("model"),
            }
            return json.dumps(
                {"health": health, "counts": counts, "config": cfg, "error": None},
                ensure_ascii=False,
            )
        except Exception as e:  # noqa: BLE001
            return json.dumps(
                {"health": {}, "counts": {}, "config": {}, "error": str(e)},
                ensure_ascii=False,
            )

    # ---- 对话历史 ----
    @Slot(result=str)
    def getThreads(self) -> str:  # noqa: N802
        try:
            return self._ok(self._memory.list_threads())
        except Exception as e:  # noqa: BLE001
            return self._err(str(e))

    @Slot(str, int, result=str)
    def getHistory(self, thread_id: str, limit: int) -> str:  # noqa: N802
        try:
            rows = self._memory.list_history(thread_id, limit)
            return self._ok({"rows": rows, "has_more": len(rows) == limit})
        except Exception as e:  # noqa: BLE001
            return self._err(str(e))

    # ---- 工作记忆 ----
    @Slot(result=str)
    def getWorkMemory(self) -> str:  # noqa: N802
        try:
            summary, recent = self._memory.load_work_memory()
            return self._ok({"summary": summary, "recent": recent})
        except Exception as e:  # noqa: BLE001
            return self._err(str(e))

    # ---- 用户画像 ----
    @Slot(result=str)
    def getProfile(self) -> str:  # noqa: N802
        try:
            return self._ok(self._memory.get_profile())
        except Exception as e:  # noqa: BLE001
            return self._err(str(e))

    # ---- 语义记忆 ----
    @Slot(int, result=str)
    def listSemantic(self, limit: int) -> str:  # noqa: N802
        try:
            return self._ok(self._memory.list_semantic(limit))
        except Exception as e:  # noqa: BLE001
            return self._err(str(e))

    # ---- Live2D 模型 ----
    @Slot(result=str)
    def listModels(self) -> str:  # noqa: N802
        try:
            models = sorted(
                p.name
                for p in self._l2d_dir.iterdir()
                if p.is_dir() and any(p.glob("*.model3.json"))
            )
            active = self._cfg.get("live2d", {}).get("model", "LSS")
            return json.dumps({"models": models, "active": active}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps(
                {"models": [], "active": None, "error": str(e)}, ensure_ascii=False
            )

    @Slot(result=str)
    def importModel(self) -> str:  # noqa: N802
        src_dir = QFileDialog.getExistingDirectory(None, "选择 Live2D 模型文件夹")
        if not src_dir:
            return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)
        model_dir = Path(src_dir).name

        def run() -> None:
            result = self._model_importer.import_folder(Path(src_dir))
            self.import_finished.emit(json.dumps(result, ensure_ascii=False))

        threading.Thread(target=run, daemon=True).start()
        return json.dumps(
            {"ok": True, "started": True, "model": model_dir}, ensure_ascii=False
        )

    @Slot(str, result=str)
    def applyModel(self, model_id: str) -> str:  # noqa: N802
        if not (self._l2d_dir / model_id).is_dir():
            return self._err(f"模型 {model_id} 不存在")
        try:
            self._cfg.setdefault("live2d", {})["model"] = model_id
            save_config(self._cfg, self._config_path)
        except Exception as e:  # noqa: BLE001
            return self._err(f"写入失败：{e}")
        self.model_changed.emit(model_id)
        return json.dumps({"ok": True, "error": None}, ensure_ascii=False)

    @Slot(str, result=str)
    def deleteModel(self, model_id: str) -> str:  # noqa: N802
        active = self._cfg.get("live2d", {}).get("model", "LSS")
        if model_id == active:
            return self._err(f"模型 {model_id} 正在使用，请先切换到其他模型")
        ret = QMessageBox.question(
            None,
            "删除模型",
            f"确定删除模型 {model_id} 吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)
        result = self._model_importer.delete_model(model_id)
        if not result.get("ok"):
            return self._err(result.get("error", "删除失败"))
        return json.dumps(
            {"ok": True, "error": None, "model": model_id}, ensure_ascii=False
        )

    # ---- 语音 ----
    @Slot(result=str)
    def getVoiceConfig(self) -> str:  # noqa: N802
        tts = self._cfg.get("voice", {}).get("tts", {})
        return json.dumps(tts, ensure_ascii=False)

    @Slot(str, result=str)
    def saveVoiceConfig(self, tts_json: str) -> str:  # noqa: N802
        try:
            tts = json.loads(tts_json)
        except Exception as e:  # noqa: BLE001
            return self._err(f"解析失败：{e}")
        provider = tts.get("provider")
        if provider not in ("edge", "http", "cosyvoice"):
            return self._err(f"未知 TTS provider：{provider}")
        self._cfg.setdefault("voice", {}).setdefault("tts", {}).update(tts)
        try:
            save_config(self._cfg, self._config_path)
        except Exception as e:  # noqa: BLE001
            return self._err(f"写入失败：{e}")
        return json.dumps({"ok": True, "error": None}, ensure_ascii=False)

    @Slot(str, str, result=str)
    def previewVoice(self, text: str, tts_json: str) -> str:  # noqa: N802
        try:
            tts = json.loads(tts_json)
            path = synthesize(text, **tts)
        except Exception as e:  # noqa: BLE001
            return self._err(str(e))
        data = path.read_bytes()
        mime = "audio/mpeg" if path.suffix == ".mp3" else "audio/wav"
        return json.dumps(
            {
                "ok": True,
                "error": None,
                "base64": base64.b64encode(data).decode("ascii"),
                "mime": mime,
            },
            ensure_ascii=False,
        )

    # ---- 配置 ----
    @Slot(result=str)
    def getConfig(self) -> str:  # noqa: N802
        llm = self._cfg.get("llm", {})
        providers = [
            {
                "name": name,
                "base_url": p.get("base_url", ""),
                "api_key_env": p.get("api_key_env", ""),
            }
            for name, p in llm.get("providers", {}).items()
        ]
        return json.dumps(
            {
                "llm": {
                    "provider": llm.get("provider"),
                    "model": llm.get("model"),
                    "providers": providers,
                },
                "live2d": {"model": self._cfg.get("live2d", {}).get("model")},
            },
            ensure_ascii=False,
        )

    @Slot(str, result=str)
    def saveConfig(self, partial_json: str) -> str:  # noqa: N802
        try:
            patch = json.loads(partial_json)
        except Exception as e:  # noqa: BLE001
            return self._err(f"解析失败：{e}")

        llm = patch.get("llm") or {}
        live2d = patch.get("live2d") or {}
        new_provider = llm.get("provider")
        new_model = llm.get("model")
        new_live2d_model = live2d.get("model")

        if new_provider:
            providers = self._cfg.get("llm", {}).get("providers", {})
            if new_provider not in providers:
                return self._err(f"未知 provider：{new_provider}")
            self._cfg.setdefault("llm", {})["provider"] = new_provider
        if new_model:
            self._cfg.setdefault("llm", {})["model"] = new_model
        if new_live2d_model:
            self._cfg.setdefault("live2d", {})["model"] = new_live2d_model

        try:
            save_config(self._cfg, self._config_path)
        except Exception as e:  # noqa: BLE001
            return self._err(f"写入失败：{e}")
        return json.dumps(
            {"ok": True, "error": None, "restart_required": True}, ensure_ascii=False
        )
