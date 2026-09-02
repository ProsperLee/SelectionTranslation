"""思维导图窗口：嵌入 web/drawnix 前端（Drawnix 白板 / 思维导图）。"""

from __future__ import annotations

import functools
import logging
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.base_window import FramelessWindow
from ui.constants import FONT_SIZE, HEADER_BTN_SIZE, ICON_SIZE, WIDGET_MARGIN_H
from ui.icons import IconButton
from ui.text_utils import disable_label_selection

logger = logging.getLogger("drawnix")

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


def drawnix_dir() -> Path:
    """开发态为仓库 web/drawnix/；打包后为 _MEIPASS/web/drawnix。"""
    rel = Path("web") / "drawnix"
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / rel
        return Path(sys.executable).resolve().parent / rel
    return Path(__file__).resolve().parent.parent / rel


def drawnix_index_path() -> Path:
    """构建产物 index.html（vite outDir: dist/apps/web）。"""
    return drawnix_dir() / "dist" / "apps" / "web" / "index.html"


def drawnix_dist_dir() -> Path:
    return drawnix_index_path().parent


_server: ThreadingHTTPServer | None = None
_server_root: Path | None = None
_server_url: str | None = None
_server_lock = threading.Lock()


def drawnix_serve_url() -> str | None:
    """在 127.0.0.1 启动静态服务，避免 file:// 下绝对路径资源 404 导致白屏。"""
    root = drawnix_dist_dir()
    if not (root / "index.html").is_file():
        return None

    global _server, _server_root, _server_url
    with _server_lock:
        if _server is not None and _server_root == root:
            return _server_url

        if _server is not None:
            _server.shutdown()
            _server = None
            _server_url = None

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        _server = httpd
        _server_root = root
        _server_url = f"http://127.0.0.1:{port}/"
        logger.info("思维导图静态服务 | root=%s url=%s", root, _server_url)
        return _server_url


class DrawnixWindow(FramelessWindow):
    """无边框窗口：居中标题，右全屏 + 关闭；内容为 QWebEngineView。"""

    def __init__(self):
        super().__init__(show_header_border=True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setWindowTitle("思维导图")
        app = QApplication.instance()
        if app is not None and "QToolTip {" not in (app.styleSheet() or ""):
            app.setStyleSheet((app.styleSheet() or "") + _TOOLTIP_QSS)
        self.setMinimumSize(860, 520)
        self.resize(1100, 700)
        self._restore_geometry = None
        self._workarea_maximized = False
        self._build_ui()
        self.enable_corner_resize(self._on_resize)
        self._load_page()

    def _on_resize(self, delta_x: int, delta_y: int) -> None:
        if self._workarea_maximized or self.isFullScreen() or self.isMaximized():
            return
        self.resize(
            max(self.minimumWidth(), self.width() + delta_x),
            max(self.minimumHeight(), self.height() + delta_y),
        )

    def _build_ui(self):
        header = QHBoxLayout()
        header.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        header.setSpacing(0)

        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        title = QLabel("思维导图")
        disable_label_selection(title)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: #ffffff; font-size: {FONT_SIZE}px; background: transparent;"
        )

        self.fullscreen_btn = IconButton(
            "restore.svg",
            size=ICON_SIZE,
            variant="light",
            button_size=HEADER_BTN_SIZE,
        )
        self.fullscreen_btn.setToolTip("全屏")
        self.close_btn = IconButton(
            "close.svg",
            size=ICON_SIZE,
            variant="light",
            button_size=HEADER_BTN_SIZE,
        )
        self.close_btn.setToolTip("关闭")

        right = QWidget()
        right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_lay = QHBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)
        right_lay.addStretch(1)
        right_lay.addWidget(self.fullscreen_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        right_lay.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header.addWidget(left, 1)
        header.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(right, 1)
        self.set_header_layout(header)

        self.web = QWebEngineView()
        settings = self.web.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )

        wrap = QWidget()
        wrap.setStyleSheet("background: #1e1e1e;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.web, 1)
        self.body.addWidget(wrap)

        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        self.close_btn.clicked.connect(self.close)
        self.web.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.error("思维导图页面加载失败 | url=%s", self.web.url().toString())

    def _load_page(self) -> None:
        url_str = drawnix_serve_url()
        if not url_str:
            path = drawnix_index_path()
            logger.error("思维导图页面缺失: %s", path)
            self.web.setHtml(
                "<html><body style='background:#1e1e1e;color:#ccc;font-family:sans-serif;padding:24px'>"
                "<p>未找到 Drawnix 构建产物。</p>"
                "<p>请先在 <code>web/drawnix</code> 目录执行 "
                "<code>npm install &amp;&amp; npm run build:web</code>。</p>"
                "</body></html>"
            )
            return
        url = QUrl(url_str)
        logger.info("打开思维导图 | url=%s", url.toString())
        self.web.setUrl(url)

    def _toggle_fullscreen(self) -> None:
        """铺满当前屏工作区（availableGeometry），不遮挡系统任务栏。"""
        if self._workarea_maximized or self.isFullScreen():
            if self.isFullScreen():
                self.showNormal()
            self._workarea_maximized = False
            if self._restore_geometry is not None:
                self.setGeometry(self._restore_geometry)
                self._restore_geometry = None
            self.fullscreen_btn.set_icon_name("restore.svg")
            self.fullscreen_btn.setToolTip("全屏")
            return

        self._restore_geometry = self.geometry()
        screen = self.screen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        else:
            self.showMaximized()
        self._workarea_maximized = True
        self.fullscreen_btn.set_icon_name("maximize.svg")
        self.fullscreen_btn.setToolTip("退出全屏")

    def _header_drag_area(self) -> bool:
        return True
