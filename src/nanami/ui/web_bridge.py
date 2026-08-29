"""QWebChannel 桥接：JS → Python 通信。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class WebBridge(QObject):
    """暴露给 JS 的对象，JS 通过 bridge.xxx 调用。"""

    user_input = Signal(str)
    character_clicked = Signal()

    @Slot(str)
    def sendUserInput(self, text: str) -> None:
        self.user_input.emit(text)

    @Slot()
    def notifyCharacterClicked(self) -> None:
        self.character_clicked.emit()
