"""系统托盘。"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def _placeholder_icon() -> QIcon:
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#ff8fa3"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.end()
    return QIcon(pm)


def create_tray(
    app: QApplication,
    window,
    open_dashboard: Callable[[], None] | None = None,
    name: str = "七海",
) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(_placeholder_icon(), app)
    tray.setToolTip(name)

    menu = QMenu()
    menu.addAction("放大", window.zoom_in)
    menu.addAction("缩小", window.zoom_out)
    menu.addAction("重置大小", window.reset_zoom)
    menu.addSeparator()
    if open_dashboard is not None:
        dash_action = menu.addAction("仪表盘")
        dash_action.triggered.connect(lambda: open_dashboard())
        menu.addSeparator()
    quit_action = menu.addAction("退出")
    quit_action.triggered.connect(app.quit)

    tray.setContextMenu(menu)
    tray.show()
    return tray
