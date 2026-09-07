"""嵌入式 WebEngine 窗口共用逻辑。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget

from ui.constants import ROOT_DIR


def web_dir(*parts: str) -> Path:
    """开发态 / 打包后统一的 web 资源根下路径。"""
    return ROOT_DIR.joinpath("web", *parts)


def configure_local_webengine(view: QWebEngineView) -> None:
    settings = view.settings()
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
    )
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
    )
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)


def setup_host_bridge(
    page: QWebEnginePage,
    host: QObject,
    *,
    script_name: str,
    bridge_js: str,
) -> None:
    """注册 QWebChannel host，并注入 qwebchannel.js + 业务 bridge 脚本。"""
    channel = QWebChannel(page)
    channel.registerObject("host", host)
    page.setWebChannel(channel)

    scripts = page.scripts()
    for name in ("qwebchannel", script_name):
        for script in list(scripts.find(name)):
            scripts.remove(script)

    qc = QWebEngineScript()
    qc.setName("qwebchannel")
    qc.setSourceUrl(QUrl("qrc:/qtwebchannel/qwebchannel.js"))
    qc.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    qc.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    qc.setRunsOnSubFrames(False)
    scripts.insert(qc)

    bridge = QWebEngineScript()
    bridge.setName(script_name)
    bridge.setSourceCode(bridge_js)
    bridge.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    bridge.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    bridge.setRunsOnSubFrames(False)
    scripts.insert(bridge)


def toggle_workarea_fullscreen(
    window: QWidget,
    *,
    maximized: bool,
    restore_geometry,
    fullscreen_btn,
) -> tuple[bool, object | None]:
    """
    铺满当前屏工作区（availableGeometry），不遮挡任务栏。
    返回 (是否工作区最大化, 恢复用 geometry)。
    """
    if maximized or window.isFullScreen():
        if window.isFullScreen():
            window.showNormal()
        if restore_geometry is not None:
            window.setGeometry(restore_geometry)
        fullscreen_btn.set_icon_name("restore.svg")
        fullscreen_btn.setToolTip("全屏")
        return False, None

    saved = window.geometry()
    screen = window.screen()
    if screen is not None:
        window.setGeometry(screen.availableGeometry())
    else:
        window.showMaximized()
    fullscreen_btn.set_icon_name("maximize.svg")
    fullscreen_btn.setToolTip("退出全屏")
    return True, saved
