"""主窗口：无边框透明置顶窗口，内嵌 Live2D + 输入栏。"""
from __future__ import annotations

import json

from PySide6.QtCore import QEvent, QUrl, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .web_bridge import WebBridge


class MainWindow(QWidget):
    user_submitted = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._drag_pos = None
        self._base_size = (360, 480)
        self._scale = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(*self._base_size)

        self.view = QWebEngineView(self)
        self.view.installEventFilter(self)
        self.view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.bridge = WebBridge()
        channel = QWebChannel(self.view.page())
        channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(channel)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("和七海说点什么…")
        self.send_btn = QPushButton("发送", self)

        input_bar = QWidget(self)
        input_bar.setObjectName("inputBar")
        bar_layout = QHBoxLayout(input_bar)
        bar_layout.setContentsMargins(8, 6, 8, 6)
        bar_layout.addWidget(self.input, 1)
        bar_layout.addWidget(self.send_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)
        layout.addWidget(input_bar)

        self._style()
        self._connect()

    def _style(self) -> None:
        self.setStyleSheet(
            """
            #inputBar {
                background: rgba(30, 30, 30, 200);
                border-radius: 10px;
                margin: 8px;
            }
            QLineEdit {
                background: rgba(255, 255, 255, 30);
                border: none;
                border-radius: 6px;
                padding: 6px 8px;
                color: white;
            }
            QPushButton {
                background: rgba(255, 255, 255, 40);
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 70); }
            """
        )

    def _connect(self) -> None:
        self.send_btn.clicked.connect(self._on_submit)
        self.input.returnPressed.connect(self._on_submit)
        self.bridge.user_input.connect(self.user_submitted)
        self.bridge.character_clicked.connect(self.input.setFocus)

    def load_url(self, url: str) -> None:
        self.view.load(QUrl(url))

    def _on_submit(self) -> None:
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.user_submitted.emit(text)

    def speak(self, text: str, emotion: str = "neutral", audio_path: str = "") -> None:
        """让角色说话：触发情绪 + 口型（JS）+ 播放语音。"""
        js = (
            "window.nanamiSpeak && "
            f"window.nanamiSpeak({json.dumps(text)}, {json.dumps(emotion)});"
        )
        self.view.page().runJavaScript(js)
        if audio_path:
            self.player.setSource(QUrl.fromLocalFile(audio_path))
            self.player.play()

    # ---- 缩放 ----
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel:
            self._on_wheel(event)
            return True
        return super().eventFilter(obj, event)

    def _on_wheel(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.1 if delta > 0 else 1 / 1.1
        self._apply_scale(self._scale * factor)
        event.accept()

    def zoom_in(self) -> None:
        self._apply_scale(self._scale * 1.15)

    def zoom_out(self) -> None:
        self._apply_scale(self._scale / 1.15)

    def reset_zoom(self) -> None:
        self._apply_scale(1.0)

    def _apply_scale(self, scale: float) -> None:
        """按比例缩放整个窗口，保持右下角锚点，避免桌宠漂移。"""
        scale = max(0.6, min(2.0, scale))
        if abs(scale - self._scale) < 1e-4:
            return
        bottom_right = self.frameGeometry().bottomRight()
        self._scale = scale
        w, h = self._base_size
        self.resize(round(w * scale), round(h * scale))
        new_bottom_right = self.frameGeometry().bottomRight()
        self.move(self.pos() + (bottom_right - new_bottom_right))

    # ---- 无边框窗口拖拽 ----
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None
        event.accept()

    def move_to_bottom_right(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 20
        y = screen.bottom() - self.height() - 20
        self.move(x, y)
