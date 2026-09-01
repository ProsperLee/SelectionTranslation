"""便签风格二次确认框。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.constants import BORDER_RADIUS, FONT_SIZE, NOTE_WINDOW_ALPHA
from ui.note_colors import contrast_text_color, is_dark_color


class NoteConfirmDialog(QDialog):
    """与便签同色半透明确认框：取消 / 确认。"""

    def __init__(
        self,
        *,
        message: str,
        content_color: QColor,
        header_color: QColor,
        confirm_text: str = "删除",
        cancel_text: str = "取消",
        parent=None,
    ):
        super().__init__(parent)
        self._content_color = QColor(content_color)
        self._header_color = QColor(header_color)
        self.setWindowTitle("确认")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(280)

        fg = contrast_text_color(self._content_color)
        dark = is_dark_color(self._content_color)
        btn_bg = "rgba(255,255,255,0.18)" if dark else "rgba(0,0,0,0.08)"
        btn_hover = "rgba(255,255,255,0.28)" if dark else "rgba(0,0,0,0.14)"
        danger_bg = "rgba(220, 60, 60, 0.85)"
        danger_hover = "rgba(200, 40, 40, 0.95)"

        root = QWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(root)

        inner = QVBoxLayout(root)
        inner.setContentsMargins(16, 16, 16, 14)
        inner.setSpacing(14)

        label = QLabel(message)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(
            f"color: {fg.name()}; font-size: {FONT_SIZE}px; background: transparent; border: none;"
        )
        inner.addWidget(label)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)

        self.cancel_btn = QPushButton(cancel_text)
        self.confirm_btn = QPushButton(confirm_text)
        for btn in (self.cancel_btn, self.confirm_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setMinimumWidth(64)

        self.cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {btn_bg};
                color: {fg.name()};
                border: none;
                border-radius: {BORDER_RADIUS}px;
                font-size: {FONT_SIZE}px;
                padding: 0 12px;
            }}
            QPushButton:hover {{ background: {btn_hover}; }}
            """
        )
        self.confirm_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {danger_bg};
                color: #ffffff;
                border: none;
                border-radius: {BORDER_RADIUS}px;
                font-size: {FONT_SIZE}px;
                padding: 0 12px;
            }}
            QPushButton:hover {{ background: {danger_hover}; }}
            """
        )
        row.addWidget(self.cancel_btn)
        row.addWidget(self.confirm_btn)
        inner.addLayout(row)

        self.cancel_btn.clicked.connect(self.reject)
        self.confirm_btn.clicked.connect(self.accept)

        root.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        root.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)

        fill = QColor(self._content_color)
        fill.setAlpha(NOTE_WINDOW_ALPHA)
        painter.fillPath(path, fill)

        header = QPainterPath()
        header.addRect(QRectF(0.5, 0.5, self.width() - 1, 8))
        painter.fillPath(path.intersected(header), self._with_alpha(self._header_color))

        border = (
            QColor(255, 255, 255, 40)
            if is_dark_color(self._content_color)
            else QColor(0, 0, 0, 45)
        )
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    @staticmethod
    def _with_alpha(color: QColor, alpha: int = NOTE_WINDOW_ALPHA) -> QColor:
        c = QColor(color)
        c.setAlpha(max(0, min(255, int(alpha))))
        return c
