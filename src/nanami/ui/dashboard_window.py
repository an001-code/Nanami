"""仪表盘窗口：第二个 QWebEngineView，普通窗口（有标题栏、进任务栏）。"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .dashboard_bridge import DashboardBridge


class DashboardWindow(QWidget):
    def __init__(self, bridge: DashboardBridge, url: str, name: str = "七海") -> None:
        super().__init__()
        self.setWindowTitle(f"{name} · 仪表盘")
        self.resize(1000, 720)

        self.view = QWebEngineView(self)
        channel = QWebChannel(self.view.page())
        channel.registerObject("bridge", bridge)
        self.view.page().setWebChannel(channel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self.view.load(QUrl(url))

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def set_pet_name(self, name: str) -> None:
        self.setWindowTitle(f"{name} · 仪表盘")
