"""运行日志查看窗口（彩色 HTML）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from app_log import (
    LOG_FONT_PX,
    MAX_AGE_SECONDS,
    clear_logs,
    get_log_html,
    get_log_text,
    log_lines_count,
)
from ui.base_window import FramelessWindow
from ui.constants import (
    BORDER_RADIUS,
    FONT_SIZE,
    HEADER_BTN_SIZE,
    WIDGET_MARGIN_H,
    WIDGET_MARGIN_V,
)
from ui.icons import IconButton, PrimaryButton
from ui.text_utils import disable_label_selection
from ui.widgets import ToastTip


class LogWindow(FramelessWindow):
    def __init__(self):
        super().__init__(show_header_border=True)
        self.setMinimumSize(560, 420)
        self.resize(680, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._auto_scroll = True
        self._build_content()

        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._refresh_if_needed)
        self._last_count = -1

    def _build_content(self):
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        title = QLabel("运行日志")
        disable_label_selection(title)
        title.setStyleSheet(
            f"color: #ffffff; font-size: {FONT_SIZE}px; background: transparent;"
        )
        self.minimize_btn = IconButton(
            "minus.svg", variant="light", button_size=HEADER_BTN_SIZE
        )
        self.minimize_btn.setToolTip("最小化")
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.close_btn = IconButton(
            "close.svg", variant="light", button_size=HEADER_BTN_SIZE
        )
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self.close)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.minimize_btn)
        header_layout.addWidget(self.close_btn)
        self.set_header_layout(header_layout)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(
            WIDGET_MARGIN_H, WIDGET_MARGIN_V, WIDGET_MARGIN_H, WIDGET_MARGIN_V
        )
        layout.setSpacing(WIDGET_MARGIN_V)

        self.viewer = QTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setAcceptRichText(True)
        self.viewer.setFont(QFont("Consolas", LOG_FONT_PX))
        # 内容框需要换行显示完整原文
        self.viewer.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.viewer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.viewer.setStyleSheet(
            f"""
            QTextEdit {{
                background: #1a1a1a;
                color: #d0d0d0;
                border: 1px solid #333333;
                border-radius: {BORDER_RADIUS}px;
                padding: 6px;
                selection-background-color: #088fff;
                selection-color: #ffffff;
            }}
            """
        )
        self.viewer.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.viewer, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(WIDGET_MARGIN_H)
        self.count_label = QLabel()
        disable_label_selection(self.count_label)
        self.count_label.setStyleSheet(f"color: #888888; font-size: {FONT_SIZE - 2}px;")
        footer.addWidget(self.count_label)
        footer.addStretch()

        refresh_btn = PrimaryButton("刷新")
        refresh_btn.clicked.connect(self.refresh)
        copy_btn = PrimaryButton("复制全部", "copy.svg")
        copy_btn.clicked.connect(self._copy_all)
        clear_btn = PrimaryButton("清空")
        clear_btn.clicked.connect(self._clear)
        footer.addWidget(refresh_btn)
        footer.addWidget(copy_btn)
        footer.addWidget(clear_btn)
        layout.addLayout(footer)

        self.body.addWidget(body)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)

    def _header_drag_area(self) -> bool:
        return True

    def _on_scroll(self, value: int):
        bar = self.viewer.verticalScrollBar()
        self._auto_scroll = value >= bar.maximum() - 4

    def _refresh_if_needed(self):
        count = log_lines_count()
        if count != self._last_count:
            self.refresh()

    def refresh(self):
        bar = self.viewer.verticalScrollBar()
        old_pos = bar.value()
        at_bottom = self._auto_scroll
        self.viewer.setHtml(get_log_html())
        self._last_count = log_lines_count()
        hours = max(1, MAX_AGE_SECONDS // 3600)
        self.count_label.setText(f"共 {self._last_count} 条 · 自动清除 {hours} 小时前")
        if at_bottom:
            bar.setValue(bar.maximum())
        else:
            bar.setValue(old_pos)

    def _copy_all(self):
        QGuiApplication.clipboard().setText(get_log_text())
        ToastTip(self, "已复制到剪贴板", duration_ms=1000).show()

    def _clear(self):
        clear_logs()
        self._auto_scroll = True
        self.refresh()
        ToastTip(self, "日志已清空", duration_ms=1000).show()
