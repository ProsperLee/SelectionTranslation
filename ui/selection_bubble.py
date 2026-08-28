"""划词后显示在选区末尾的翻译浮动按钮。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ui.constants import (
    BORDER_RADIUS,
    SELECTION_BUBBLE_ICON,
    SELECTION_BUBBLE_SIZE,
)
from ui.icons import ICON_ACCENT, load_icon
from ui.screen_coords import physical_global_to_qt, qt_screen_at_physical


class SelectionBubble(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(SELECTION_BUBBLE_SIZE, SELECTION_BUBBLE_SIZE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._btn = QPushButton(self)
        self._btn.setFixedSize(SELECTION_BUBBLE_SIZE, SELECTION_BUBBLE_SIZE)
        self._btn.setIconSize(QSize(SELECTION_BUBBLE_ICON, SELECTION_BUBBLE_ICON))
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.setIcon(load_icon("translate.svg", SELECTION_BUBBLE_ICON, ICON_ACCENT))
        self._btn.setStyleSheet(
            f"""
            QPushButton {{
                background: rgba(33, 33, 33, 0.92);
                border: 1px solid #3a3a3a;
                border-radius: {BORDER_RADIUS}px;
            }}
            QPushButton:hover {{
                background: rgba(48, 48, 48, 0.95);
                border: 1px solid #4a4a4a;
            }}
            QPushButton:pressed {{
                background: rgba(58, 58, 58, 0.98);
            }}
            """
        )
        self._btn.clicked.connect(self.clicked.emit)
        layout.addWidget(self._btn)

        self._text = ""
        self._anchor_physical: tuple[int, int] | None = None
        self.hide()

    def selection_text(self) -> str:
        return self._text

    def anchor_physical(self) -> tuple[int, int] | None:
        return self._anchor_physical

    def popup_at(self, x: int, y: int, text: str):
        self._text = text
        self._anchor_physical = (int(x), int(y))
        if not self._text:
            self.dismiss()
            return
        qx, qy = physical_global_to_qt(x, y)
        screen = qt_screen_at_physical(x, y) or self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            qx = min(max(geo.left(), qx), geo.right() - self.width() + 1)
            qy = min(max(geo.top(), qy), geo.bottom() - self.height() + 1)
        self.move(int(qx), int(qy))
        self.show()
        self.raise_()

    def contains_point(self, x: int, y: int) -> bool:
        if not self.isVisible():
            return False
        qx, qy = physical_global_to_qt(x, y)
        rect = self.frameGeometry()
        return rect.contains(qx, qy)

    def dismiss(self):
        self._text = ""
        self._anchor_physical = None
        self.hide()
