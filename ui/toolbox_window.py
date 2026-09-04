"""工具箱主窗口（PySide 原生）。"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.base_window import FramelessWindow
from ui.constants import FONT_SIZE, HEADER_BTN_SIZE, ICON_SIZE, WIDGET_MARGIN_H
from ui.icons import IconButton, load_pixmap
from ui.toolbox_img_base64 import ImgBase64Page
from ui.toolbox_qrcode import QrcodePage
from ui.toolbox_regex import RegexPage
from ui.toolbox_widgets import EDGE_SCROLLBAR_QSS, SideMenuButton
from ui.text_utils import disable_label_selection

logger = logging.getLogger("toolbox")

_TOOLTIP_QSS = """
QToolTip {
    font-size: 12px;
    font-family: "Microsoft YaHei UI";
    padding: 4px 8px;
    color: #e8e8e8;
    background-color: #2d2d2d;
    border: 1px solid #454545;
    border-radius: 4px;
}
"""

_TOOLS = (
    ("img-base64", "image.svg", "图片-Base64"),
    ("qrcode", "qrcode.svg", "二维码生成"),
    ("regex", "regex.svg", "正则表达式"),
)


class ToolboxWindow(FramelessWindow):
    """无边框工具箱：左侧菜单 + 右侧工具页。"""

    def __init__(self):
        super().__init__(show_header_border=True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setWindowTitle("工具箱")
        app = QApplication.instance()
        if app is not None and "QToolTip {" not in (app.styleSheet() or ""):
            app.setStyleSheet((app.styleSheet() or "") + _TOOLTIP_QSS)
        self.setMinimumSize(900, 560)
        self.resize(1100, 700)
        self._restore_geometry = None
        self._workarea_maximized = False
        self._menu_btns: list[SideMenuButton] = []
        self._build_ui()
        self.enable_corner_resize(self._on_resize)
        self._switch("img-base64")

    def _on_resize(self, dx: int, dy: int) -> None:
        if self._workarea_maximized or self.isFullScreen() or self.isMaximized():
            return
        self.resize(
            max(self.minimumWidth(), self.width() + dx),
            max(self.minimumHeight(), self.height() + dy),
        )

    def _build_ui(self) -> None:
        header = QHBoxLayout()
        header.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        header.setSpacing(0)

        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        title = QLabel("工具箱")
        disable_label_selection(title)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:#ffffff;font-size:{FONT_SIZE}px;background:transparent;"
        )

        self.minimize_btn = IconButton(
            "minus.svg", size=ICON_SIZE, variant="light", button_size=HEADER_BTN_SIZE
        )
        self.minimize_btn.setToolTip("最小化")
        self.fullscreen_btn = IconButton(
            "restore.svg", size=ICON_SIZE, variant="light", button_size=HEADER_BTN_SIZE
        )
        self.fullscreen_btn.setToolTip("全屏")
        self.close_btn = IconButton(
            "close.svg", size=ICON_SIZE, variant="light", button_size=HEADER_BTN_SIZE
        )
        self.close_btn.setToolTip("关闭")

        right = QWidget()
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_lay = QHBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)
        right_lay.addStretch(1)
        right_lay.addWidget(self.minimize_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        right_lay.addWidget(self.fullscreen_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        right_lay.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header.addWidget(left, 1)
        header.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(right, 1)
        self.set_header_layout(header)

        body = QWidget()
        body.setStyleSheet(f"background:#212121;{EDGE_SCROLLBAR_QSS}")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # 侧栏
        side = QWidget()
        side.setFixedWidth(168)
        side.setStyleSheet("background:#1a1a1a;border-right:1px solid #2a2a2a;")
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(8, 10, 8, 10)
        side_lay.setSpacing(4)
        for tool_id, icon, name in _TOOLS:
            btn = SideMenuButton(icon, name, tool_id)
            btn.clicked.connect(lambda _=False, tid=tool_id: self._switch(tid))
            side_lay.addWidget(btn)
            self._menu_btns.append(btn)
        side_lay.addStretch(1)
        body_lay.addWidget(side)

        # 主区
        main = QWidget()
        main.setStyleSheet("background:#212121;")
        main_lay = QVBoxLayout(main)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        main_header = QWidget()
        main_header.setFixedHeight(44)
        main_header.setStyleSheet("background:#212121;border-bottom:1px solid #2a2a2a;")
        mh = QHBoxLayout(main_header)
        mh.setContentsMargins(16, 0, 16, 0)
        mh.setSpacing(8)
        self._main_icon = QLabel()
        self._main_icon.setFixedSize(16, 16)
        self._main_title = QLabel("图片-Base64")
        disable_label_selection(self._main_title)
        self._main_title.setStyleSheet(
            "color:#ffffff;font-size:14px;font-weight:500;background:transparent;"
        )
        mh.addWidget(self._main_icon)
        mh.addWidget(self._main_title)
        mh.addStretch(1)
        main_lay.addWidget(main_header)

        content = QWidget()
        content.setStyleSheet(f"background:#212121;{EDGE_SCROLLBAR_QSS}")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(16, 16, 2, 16)  # 滚动条贴窗口右缘
        self._stack = QStackedWidget()
        self._page_img = ImgBase64Page()
        self._page_qr = QrcodePage()
        self._page_re = RegexPage()
        self._stack.addWidget(self._page_img)
        self._stack.addWidget(self._page_qr)
        self._stack.addWidget(self._page_re)
        content_lay.addWidget(self._stack)
        main_lay.addWidget(content, 1)

        body_lay.addWidget(main, 1)
        self.body.addWidget(body)

        self.minimize_btn.clicked.connect(self.showMinimized)
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        self.close_btn.clicked.connect(self.close)

        # 全局粘贴图片到编码页
        QShortcut(QKeySequence.StandardKey.Paste, self, activated=self._on_paste)

    def _header_drag_area(self) -> bool:
        return True

    def _switch(self, tool_id: str) -> None:
        idx = {"img-base64": 0, "qrcode": 1, "regex": 2}.get(tool_id, 0)
        self._stack.setCurrentIndex(idx)
        for btn in self._menu_btns:
            btn.set_active(btn.tool_id == tool_id)
        name = next((n for tid, _, n in _TOOLS if tid == tool_id), "工具箱")
        icon = next((ic for tid, ic, _ in _TOOLS if tid == tool_id), "image.svg")
        self._main_title.setText(name)
        self._main_icon.setPixmap(load_pixmap(icon, 16, "#e8e8e8"))

    def _on_paste(self) -> None:
        if self._stack.currentWidget() is self._page_img:
            self._page_img.try_paste_image()

    def _toggle_fullscreen(self) -> None:
        if self._workarea_maximized:
            self._workarea_maximized = False
            if self._restore_geometry is not None:
                self.setGeometry(self._restore_geometry)
            self.fullscreen_btn.set_icon_name("restore.svg")
            self.fullscreen_btn.setToolTip("全屏")
            return
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        self._restore_geometry = self.geometry()
        self.setGeometry(screen.availableGeometry())
        self._workarea_maximized = True
        self.fullscreen_btn.set_icon_name("maximize.svg")
        self.fullscreen_btn.setToolTip("退出全屏")
