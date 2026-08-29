"""应用入口：组装配置、agent、UI，并启动事件循环。"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import redis
from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Q_RETURN_ARG, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from .agent.agent import NanamiAgent
from .agent.llm import build_llm
from .config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, load_config, resolve_api_key
from .memory.embedder import QwenEmbedder
from .memory.history import ConversationHistory
from .memory.manager import MemoryManager
from .memory.profile import ProfileManager, ProfileStore
from .memory.summarizer import MemorySummarizer
from .memory.vector_store import VectorStore
from .memory.work_memory import WorkMemory
from .permissions.policy import PermissionPolicy
from .tools.registry import build_tools
from .ui.dashboard_bridge import DashboardBridge
from .ui.dashboard_window import DashboardWindow
from .ui.httpserver import StaticServer
from .ui.main_window import MainWindow
from .ui.tray import create_tray
from .voice.tts import synthesize


class PermissionAsker(QObject):
    """在主线程弹窗询问权限，供后台线程通过阻塞调用使用。"""

    @Slot(str, result=str)
    def ask(self, tool_name: str) -> str:
        ret = QMessageBox.question(
            None,
            "权限请求",
            f"宠物想要执行操作「{tool_name}」，是否允许？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return "allow" if ret == QMessageBox.StandardButton.Yes else "deny"


def make_ask_callback(asker: PermissionAsker):
    def ask(tool_name: str, args: dict) -> bool:
        result = QMetaObject.invokeMethod(
            asker,
            "ask",
            Qt.ConnectionType.BlockingQueuedConnection,
            Q_RETURN_ARG(str),
            Q_ARG(str, tool_name),
        )
        return result == "allow"

    return ask


class AgentRunner(QObject):
    """在后台线程运行 agent + TTS 合成，避免阻塞 UI。"""

    reply_ready = Signal(str, str, str)  # text, emotion, audio_path

    def __init__(self, agent: NanamiAgent, cfg: dict) -> None:
        super().__init__()
        self.agent = agent
        self.cfg = cfg

    def ask(self, text: str) -> None:
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def _run(self, text: str) -> None:
        try:
            reply, emotion = self.agent.chat(text)
        except Exception as e:  # noqa: BLE001 - 顶层兜底，避免线程静默崩溃
            reply, emotion = f"（出错了）{e}", "neutral"
        audio = self._synthesize(reply)
        self.reply_ready.emit(reply, emotion, audio)

    def _synthesize(self, text: str) -> str:
        try:
            v = self.cfg["voice"]["tts"]
            return str(
                synthesize(
                    text,
                    voice=v["voice"],
                    rate=v.get("rate", "+0%"),
                    volume=v.get("volume", "+0%"),
                )
            )
        except Exception:  # noqa: BLE001 - TTS 失败不影响文字回复
            return ""


def _resolve(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _build_memory(cfg: dict) -> MemoryManager:
    """装配记忆体系：语义记忆 / 工作记忆 / 画像 / 历史。"""
    mem_cfg = cfg["memory"]

    emb_cfg = mem_cfg["embedding"]
    provider = cfg["llm"]["providers"][emb_cfg.get("provider", "qwen")]
    embedder = QwenEmbedder(
        api_key=resolve_api_key(provider),
        base_url=provider["base_url"],
        model=emb_cfg.get("model", "text-embedding-v3"),
        dimensions=emb_cfg.get("dimensions"),
        batch_size=emb_cfg.get("batch_size", 16),
    )
    vs = VectorStore(
        _resolve(mem_cfg["vector"]["path"]),
        embedder,
        mem_cfg["vector"]["collection"],
    )
    redis_client = redis.Redis.from_url(mem_cfg["redis"]["url"], decode_responses=True)
    wm = WorkMemory(
        redis_client,
        mem_cfg["redis"]["key_prefix"],
        **mem_cfg["work_memory"],
    )
    pm = ProfileManager(
        ProfileStore(redis_client, mem_cfg["redis"]["key_prefix"] + "profile")
    )
    history = ConversationHistory(mem_cfg["postgres"]["dsn"])
    summarizer = MemorySummarizer(build_llm(cfg, temperature=0))
    return MemoryManager(cfg, vs, wm, pm, summarizer, history)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    cfg = load_config()

    # Qt 应用需先于权限弹窗与 UI 创建
    app = QApplication(argv)

    # 权限
    asker = PermissionAsker()
    perm = cfg["permissions"]
    policy = PermissionPolicy(
        default=perm.get("default", "ask"),
        allowlist=perm.get("allowlist", []),
        denylist=perm.get("denylist", []),
        ask_callback=make_ask_callback(asker),
    )

    # 记忆 + Agent（resolve_api_key 可能抛 ValueError，需在 UI 报错）
    try:
        memory = _build_memory(cfg)
        tools = build_tools(cfg)
        tools.append(memory.make_remember_tool())
        agent = NanamiAgent(cfg, tools, memory, policy)
    except ValueError as e:
        QMessageBox.critical(None, "配置错误", str(e))
        return 1

    # 静态资源 HTTP server（Live2D 模型需 HTTP 访问）
    static_dir = PROJECT_ROOT / "src" / "nanami" / "live2d" / "static"
    server = StaticServer(static_dir)
    server.start()

    model = cfg.get("live2d", {}).get("model", "LSS")

    # 仪表盘（第二窗口，托盘菜单打开；不自动显示）
    dashboard_bridge = DashboardBridge(
        memory, cfg, DEFAULT_CONFIG_PATH, static_dir / "l2d"
    )
    dashboard = DashboardWindow(
        dashboard_bridge, f"{server.base_url}/dashboard/index.html"
    )

    # UI
    window = MainWindow()
    window.load_url(f"{server.base_url}/index.html?model={model}")
    runner = AgentRunner(agent, cfg)
    runner.reply_ready.connect(window.speak)
    window.user_submitted.connect(runner.ask)

    tray = create_tray(app, window, open_dashboard=dashboard.show_and_raise)
    window.move_to_bottom_right()
    window.show()

    exit_code = app.exec()
    agent.close()
    server.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
