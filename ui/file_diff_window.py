"""文件对比窗口：嵌入 file_diff 前端（三栏合并 / 并排 Diff）。"""

from __future__ import annotations

import json
import logging
import sys
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

logger = logging.getLogger("file_diff")

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
      window.__fileDiffPost = function (payload) {
        host.receive(typeof payload === "string" ? payload : JSON.stringify(payload));
      };
    });
  }
  wire();
})();
"""


def file_diff_dir() -> Path:
    """开发态为仓库 file_diff/；打包后为 _MEIPASS/file_diff。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "file_diff"
        return Path(sys.executable).resolve().parent / "file_diff"
    return Path(__file__).resolve().parent.parent / "file_diff"


class _FileDiffBridge(QObject):
    """前端 vscodeApi.postMessage → Qt。"""

    def __init__(self, window: "FileDiffWindow"):
        super().__init__(window)
        self._window = window

    @Slot(str)
    def receive(self, payload: str) -> None:
        try:
            message = json.loads(payload)
        except Exception:
            logger.exception("文件对比消息解析失败")
            return
        self._window._on_webview_message(message)


class FileDiffWindow(FramelessWindow):
    """无边框窗口：左切换 3/2 栏，右全屏 + 关闭；内容为 QWebEngineView。"""

    def __init__(self):
        super().__init__(show_header_border=True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setWindowTitle("文件对比")
        # QToolTip 是独立顶层窗，样式必须挂在 QApplication 上才生效
        app = QApplication.instance()
        if app is not None and "QToolTip {" not in (app.styleSheet() or ""):
            app.setStyleSheet((app.styleSheet() or "") + _TOOLTIP_QSS)
        self.setMinimumSize(860, 520)
        self.resize(1100, 700)
        self._mode = "merge"  # "diff" | "merge"
        self._restore_geometry = None
        self._build_ui()
        self.enable_corner_resize(self._on_resize)
        self._load_mode(self._mode)

    def _on_resize(self, delta_x: int, delta_y: int) -> None:
        if self.isFullScreen() or self.isMaximized():
            return
        self.resize(
            max(self.minimumWidth(), self.width() + delta_x),
            max(self.minimumHeight(), self.height() + delta_y),
        )

    def _build_ui(self):
        header = QHBoxLayout()
        header.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        header.setSpacing(0)

        self.layout3_btn = IconButton(
            "layout_3.svg",
            size=ICON_SIZE,
            variant="light",
            button_size=HEADER_BTN_SIZE,
        )
        self.layout3_btn.setToolTip("三栏合并")
        self.layout2_btn = IconButton(
            "layout_2.svg",
            size=ICON_SIZE,
            variant="light",
            button_size=HEADER_BTN_SIZE,
        )
        self.layout2_btn.setToolTip("并排对比")

        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left_lay = QHBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)
        left_lay.addWidget(self.layout3_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        left_lay.addWidget(self.layout2_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        left_lay.addStretch(1)

        title = QLabel("文件对比")
        disable_label_selection(title)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: #ffffff; font-size: {FONT_SIZE}px; background: transparent;"
        )

        # 窗口态：四角收拢图标 → 进入全屏；全屏态：叠方 → 退出全屏
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

        self.layout3_btn.clicked.connect(lambda: self._switch_mode("merge"))
        self.layout2_btn.clicked.connect(lambda: self._switch_mode("diff"))
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        self.close_btn.clicked.connect(self.close)
        self._sync_mode_buttons()

    def _setup_web_bridge(self) -> None:
        page = self.web.page()
        self._bridge = _FileDiffBridge(self)
        channel = QWebChannel(page)
        channel.registerObject("host", self._bridge)
        page.setWebChannel(channel)

        scripts = page.scripts()
        for name in ("qwebchannel", "file-diff-bridge"):
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
        bridge.setName("file-diff-bridge")
        bridge.setSourceCode(_BRIDGE_JS)
        bridge.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        bridge.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        bridge.setRunsOnSubFrames(False)
        scripts.insert(bridge)

    def _page_path(self, mode: str) -> Path:
        root = file_diff_dir()
        name = "index.html" if mode == "merge" else "diff.html"
        return root / name

    def _load_mode(self, mode: str) -> None:
        path = self._page_path(mode)
        if not path.is_file():
            logger.error("文件对比页面缺失: %s", path)
            self.web.setHtml(
                "<html><body style='background:#1e1e1e;color:#ccc;font-family:sans-serif;padding:24px'>"
                f"<p>未找到 {path.name}。</p>"
                "<p>请先在 file_diff 目录执行 <code>npm install &amp;&amp; npm run build</code>。</p>"
                "</body></html>"
            )
            return
        dist_js = file_diff_dir() / "dist" / "webview" / "main.js"
        if not dist_js.is_file():
            logger.error("文件对比前端未构建: %s", dist_js)
            self.web.setHtml(
                "<html><body style='background:#1e1e1e;color:#ccc;font-family:sans-serif;padding:24px'>"
                "<p>前端尚未构建。</p>"
                "<p>请在 <code>file_diff</code> 目录执行 <code>npm install &amp;&amp; npm run build</code> 后重试。</p>"
                "</body></html>"
            )
            return
        self._mode = mode
        self._sync_mode_buttons()
        url = QUrl.fromLocalFile(str(path.resolve()))
        logger.info("打开文件对比 | mode=%s url=%s", mode, url.toString())
        self.web.setUrl(url)

    def _switch_mode(self, mode: str) -> None:
        if mode == self._mode and self.web.url().isValid() and not self.web.url().isEmpty():
            return
        self._load_mode(mode)

    def _sync_mode_buttons(self) -> None:
        self.layout3_btn.set_active(self._mode == "merge")
        self.layout2_btn.set_active(self._mode == "diff")

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            if self._restore_geometry is not None:
                self.setGeometry(self._restore_geometry)
                self._restore_geometry = None
            self.fullscreen_btn.set_icon_name("restore.svg")
            self.fullscreen_btn.setToolTip("全屏")
            return
        self._restore_geometry = self.geometry()
        self.showFullScreen()
        self.fullscreen_btn.set_icon_name("maximize.svg")
        self.fullscreen_btn.setToolTip("退出全屏")

    def _on_webview_message(self, message: dict) -> None:
        msg_type = message.get("type")
        if msg_type == "cancel":
            # 与右上角关闭按钮相同：直接关窗
            self.close()
            return
        if msg_type == "apply":
            text = message.get("text", "")
            if not isinstance(text, str):
                text = ""
            suggested = message.get("fileName")
            if not isinstance(suggested, str) or not suggested.strip():
                suggested = "result.txt"
            self._save_apply_text(text, suggested.strip())

    def _save_apply_text(self, text: str, suggested_name: str = "result.txt") -> None:
        name = Path(suggested_name.replace("\\", "/")).name or "result.txt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存对比结果",
            name,
            "所有文件 (*.*);;文本文件 (*.txt)",
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
            logger.info("文件对比已保存 | path=%s bytes=%d", path, len(text.encode("utf-8")))
            self.web.page().runJavaScript(
                'window.postMessage({ type: "applied", staged: false }, "*");'
            )
        except Exception:
            logger.exception("保存对比结果失败 | path=%s", path)

    def _header_drag_area(self) -> bool:
        return True
