"""关于窗口：Logo、版本、作者。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.app_version import get_app_version
from ui.base_window import FramelessWindow
from ui.constants import FONT_SIZE, HEADER_BTN_SIZE, WIDGET_MARGIN_H
from ui.icons import ICON_ACCENT, IconButton, load_pixmap
from ui.text_utils import disable_label_selection

_LOGO_SIZE = 28
_AUTHOR_FONT_SIZE = 11


class AboutWindow(FramelessWindow):
    def __init__(self):
        super().__init__(show_header_border=False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("关于")
        self.setFixedSize(120, 120)
        self._build_ui()

    def _build_ui(self) -> None:
        header = QHBoxLayout()
        header.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        header.addStretch(1)

        self.close_btn = IconButton(
            "close.svg",
            variant="light",
            button_size=HEADER_BTN_SIZE,
        )
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self.close)
        header.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.set_header_layout(header)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(12, 0, 12, 14)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(load_pixmap("translate.svg", _LOGO_SIZE, ICON_ACCENT))
        logo.setStyleSheet("background: transparent;")
        lay.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)

        version = QLabel(f"v{get_app_version()}")
        disable_label_selection(version)
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(
            f"color: #e8e8e8; font-size: {FONT_SIZE}px; background: transparent;"
        )
        lay.addWidget(version, 0, Qt.AlignmentFlag.AlignCenter)

        author = QLabel("by ProsperLee")
        disable_label_selection(author)
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author.setStyleSheet(
            f"color: #959595; font-size: {_AUTHOR_FONT_SIZE}px; background: transparent;"
        )
        lay.addWidget(author, 0, Qt.AlignmentFlag.AlignCenter)

        self.body.addWidget(content, 1, Qt.AlignmentFlag.AlignCenter)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )
