"""思维导图窗口：嵌入 web/drawnix 前端（Drawnix 白板 / 思维导图）。"""

from __future__ import annotations

import base64
import functools
import logging
import socket
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
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


_BRIDGE_JS = """
(function () {
  function wire() {
    if (typeof QWebChannel === "undefined" || typeof qt === "undefined") {
      setTimeout(wire, 40);
      return;
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
      var host = channel.objects.host;
      window.__drawnixHost = {
        saveBlob: function (dataUrl, filename, mime) {
          host.saveBlob(dataUrl, filename, mime);
        }
      };
    });
  }
  wire();
})();
"""


class _DrawnixBridge(QObject):
    """前端导出图片 → Qt 保存对话框。"""

    def __init__(self, window: "DrawnixWindow"):
        super().__init__(window)
        self._window = window

    @Slot(str, str, str)
    def saveBlob(self, data_url: str, filename: str, mime_type: str) -> None:
        self._window._save_blob(data_url, filename, mime_type)


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


def _index_uses_absolute_asset_urls(index_html: Path) -> bool:
    """有 <base href="/"> 或 /assets/ 绝对路径时，file:// 会白屏，需走本地 HTTP。"""
    try:
        text = index_html.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True
    if 'base href="/"' in text or "base href='/' " in text or "base href='/'" in text:
        return True
    if 'src="/assets/' in text or 'href="/assets/' in text:
        return True
    return False


_server: ThreadingHTTPServer | None = None
_server_root: Path | None = None
_server_url: str | None = None
_server_lock = threading.Lock()


class _QuietDrawnixHandler(SimpleHTTPRequestHandler):
    """打包无控制台时写 stderr 会触发连接被掐断（ERR_EMPTY_RESPONSE）。"""

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.debug("drawnix-http | " + format, *args)

    def log_error(self, format: str, *args) -> None:  # noqa: A003
        logger.warning("drawnix-http | " + format, *args)


def drawnix_serve_url() -> str | None:
    """在 127.0.0.1 启动静态服务（仅绝对资源路径构建产物需要）。"""
    root = drawnix_dist_dir()
    if not (root / "index.html").is_file():
        return None

    global _server, _server_root, _server_url
    with _server_lock:
        if _server is not None and _server_root == root and _server_url:
            return _server_url

        if _server is not None:
            try:
                _server.shutdown()
            except Exception:
                logger.exception("关闭旧思维导图静态服务失败")
            _server = None
            _server_url = None

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        handler = functools.partial(_QuietDrawnixHandler, directory=str(root))
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        ready = threading.Event()

        def _run() -> None:
            ready.set()
            try:
                httpd.serve_forever(poll_interval=0.2)
            except Exception:
                logger.exception("思维导图静态服务异常退出")

        threading.Thread(target=_run, daemon=True, name="drawnix-http").start()
        if not ready.wait(timeout=2.0):
            logger.error("思维导图静态服务启动超时")
            return None

        _server = httpd
        _server_root = root
        _server_url = f"http://127.0.0.1:{port}/"
        logger.info("思维导图静态服务 | root=%s url=%s", root, _server_url)
        return _server_url


def drawnix_page_url() -> QUrl | None:
    path = drawnix_index_path()
    if not path.is_file():
        return None
    if _index_uses_absolute_asset_urls(path):
        url_str = drawnix_serve_url()
        return QUrl(url_str) if url_str else None
    # 相对资源：file:// 即可，避免打包态本地 HTTP 踩坑
    return QUrl.fromLocalFile(str(path.resolve()))


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
        self._setup_web_bridge()

        wrap = QWidget()
        wrap.setStyleSheet("background: #1e1e1e;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.web, 1)
        self.body.addWidget(wrap)

        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        self.close_btn.clicked.connect(self.close)
        self.web.loadFinished.connect(self._on_load_finished)

    def _setup_web_bridge(self) -> None:
        page = self.web.page()
        self._bridge = _DrawnixBridge(self)
        channel = QWebChannel(page)
        channel.registerObject("host", self._bridge)
        page.setWebChannel(channel)

        scripts = page.scripts()
        for name in ("qwebchannel", "drawnix-bridge"):
            existing = scripts.find(name)
            for script in list(existing):
                scripts.remove(script)

        qc = QWebEngineScript()
        qc.setName("qwebchannel")
        qc.setSourceUrl(QUrl("qrc:/qtwebchannel/qwebchannel.js"))
        qc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        qc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        qc.setRunsOnSubFrames(False)
        scripts.insert(qc)

        bridge = QWebEngineScript()
        bridge.setName("drawnix-bridge")
        bridge.setSourceCode(_BRIDGE_JS)
        bridge.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        bridge.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        bridge.setRunsOnSubFrames(False)
        scripts.insert(bridge)

    def _save_blob(self, data_url: str, filename: str, mime_type: str) -> None:
        try:
            if "," not in data_url:
                raise ValueError("invalid data url")
            _, b64 = data_url.split(",", 1)
            data = base64.b64decode(b64)
        except Exception:
            logger.exception("思维导图导出数据解析失败")
            return

        name = Path(filename.replace("\\", "/")).name or "drawnix.png"
        ext = Path(name).suffix.lower()
        if ext == ".png":
            filter_str = "PNG 图片 (*.png);;所有文件 (*.*)"
        elif ext == ".svg":
            filter_str = "SVG 图片 (*.svg);;所有文件 (*.*)"
        else:
            filter_str = "所有文件 (*.*)"

        path, _ = QFileDialog.getSaveFileName(self, "导出图片", name, filter_str)
        if not path:
            return
        try:
            Path(path).write_bytes(data)
            logger.info(
                "思维导图已导出 | path=%s mime=%s bytes=%d",
                path,
                mime_type,
                len(data),
            )
        except Exception:
            logger.exception("思维导图导出失败 | path=%s", path)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            logger.error("思维导图页面加载失败 | url=%s", self.web.url().toString())

    def _load_page(self) -> None:
        url = drawnix_page_url()
        if url is None:
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
