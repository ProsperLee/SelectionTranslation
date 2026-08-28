"""
主应用：系统托盘常驻、全局热键、划词 / OCR 流程协调。

核心流程：
1. 划词快捷键 → 不抢焦点贴鼠标开窗 → 后台抓选区 → 再激活并自动翻译
2. 划词浮动按钮 → 用已缓存文本打开翻译窗（贴按钮位置）
3. OCR 快捷键 → 框选截图 → OCR 窗贴鼠标 → 识别后自动翻译
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app_log import (
    PURGE_INTERVAL_SECONDS,
    log_captured_content,
    purge_expired_logs,
    setup_logging,
)
from boot import reconcile_start_on_boot, set_start_on_boot
from config import CONFIG_FILE, load_config, settings_lock_active
from hotkeys import HotkeyManager
from ocr import HAS_OCR, OCR_IMPORT_ERROR
from ocr_task import OcrTask
from screenshot_selector import ScreenshotSelector
from selection import force_foreground, foreground_hwnd, peek_selection
from selection_bubble_watcher import SelectionBubbleWatcher
from selection_task import SelectionCaptureTask
from ui.constants import FONT_SIZE, TRAY_FONT_SIZE
from ui.icons import load_app_icon
from ui.log_window import LogWindow
from ui.ocr_window import OCRWindow
from ui.screen_coords import cursor_physical_pos, place_window_near_physical
from ui.settings_window import SettingsWindow
from ui.translation_window import TranslationWindow

logger = logging.getLogger("app")


def _qt_alive(obj) -> bool:
    """PySide 对象在 C++ 侧已销毁时返回 False。"""
    if obj is None:
        return False
    try:
        from shiboken6 import isValid

        return bool(isValid(obj))
    except Exception:
        try:
            obj.objectName()
            return True
        except RuntimeError:
            return False


class SelectionTranslationApp(QObject):
    def __init__(self, qt_app: QApplication):
        super().__init__(qt_app)
        self._app = qt_app
        self._config = load_config()
        self._config_mtime = self._config_mtime_value()

        self._translation_window: TranslationWindow | None = None
        self._ocr_window: OCRWindow | None = None
        self._settings_window: SettingsWindow | None = None
        self._log_window: LogWindow | None = None
        self._ocr_task: OcrTask | None = None
        self._selection_task: SelectionCaptureTask | None = None
        self._selection_token = 0
        self._ocr_token = 0

        self._hotkeys = HotkeyManager(self)
        self._hotkeys.translation_triggered.connect(self.open_translation)
        self._hotkeys.ocr_triggered.connect(self.start_ocr_capture)
        self._hotkeys.registration_failed.connect(self._on_hotkey_error)

        self._bubble_watcher = SelectionBubbleWatcher(
            self,
            peek_selection=peek_selection,
            is_blocked=self._selection_bubble_blocked,
        )
        self._bubble_watcher.translate_requested.connect(self._on_bubble_translate)

        self._tray = QSystemTrayIcon(self)
        self._app_icon = load_app_icon()
        self._tray.setIcon(self._app_icon)
        self._tray.setToolTip("划词翻译")
        self._app.setWindowIcon(self._app_icon)

        menu = QMenu()
        menu.setFont(QFont("Microsoft YaHei UI", TRAY_FONT_SIZE))
        open_settings = QAction("打开设置", menu)
        open_settings.triggered.connect(self.open_settings)
        view_logs = QAction("查看日志", menu)
        view_logs.triggered.connect(self.open_logs)
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(open_settings)
        menu.addAction(view_logs)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        self._apply_hotkeys_from_config()
        # 与安装包写入的注册表自启对齐，再刷新配置（避免设置页显示未勾选）
        enabled = reconcile_start_on_boot()
        self._config = load_config()
        self._config["start_on_boot"] = enabled
        QTimer.singleShot(300, self._sync_selection_bubble)
        self._hotkeys.start()
        logger.info(
            "应用已启动 | 划词=%s OCR=%s 划词按钮=%s 开机自启=%s",
            self._config.get("hotkey"),
            self._config.get("ocr_hotkey"),
            bool(self._config.get("selection_bubble", False)),
            enabled,
        )

        self._config_timer = QTimer(self)
        self._config_timer.setInterval(500)
        self._config_timer.timeout.connect(self._poll_config)
        self._config_timer.start()

        # 定期清除过期日志（默认 6 小时前）
        self._log_purge_timer = QTimer(self)
        self._log_purge_timer.setInterval(int(PURGE_INTERVAL_SECONDS * 1000))
        self._log_purge_timer.timeout.connect(purge_expired_logs)
        self._log_purge_timer.start()
        QTimer.singleShot(30_000, purge_expired_logs)

    def _config_mtime_value(self) -> float:
        try:
            return CONFIG_FILE.stat().st_mtime
        except OSError:
            return 0.0

    def _apply_hotkeys_from_config(self) -> None:
        config = load_config()
        self._config = config
        self._hotkeys.set_hotkeys(config["hotkey"], config["ocr_hotkey"])

    def _sync_selection_bubble(self) -> None:
        enabled = bool(self._config.get("selection_bubble", False))
        self._bubble_watcher.set_enabled(enabled)

    def _selection_bubble_blocked(self) -> bool:
        """设置页改快捷键 / OCR 截图期间不弹出划词按钮。"""
        if settings_lock_active():
            return True
        if ScreenshotSelector.suppresses_bubble():
            return True
        return False

    def _poll_config(self) -> None:
        if settings_lock_active():
            self._hotkeys.set_paused(True)
            return

        mtime = self._config_mtime_value()
        if mtime != self._config_mtime:
            self._config_mtime = mtime
            config = load_config()
            self._config = config
            self._hotkeys.set_paused(False)
            self._hotkeys.set_hotkeys(config["hotkey"], config["ocr_hotkey"])
            self._sync_selection_bubble()
            return

        if self._hotkeys.is_paused() and not settings_lock_active():
            self._hotkeys.set_paused(False)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_settings()

    def _on_hotkey_error(self, message: str):
        logger.error("快捷键注册失败: %s", message)
        self._tray.showMessage("划词翻译", message, QSystemTrayIcon.MessageIcon.Warning, 4000)

    def open_settings(self):
        if self._settings_window is None or not _qt_alive(self._settings_window):
            self._settings_window = SettingsWindow()
            self._settings_window.config_saved.connect(self._on_settings_saved)
            self._settings_window.destroyed.connect(self._clear_settings_window)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()
        logger.info("打开设置")

    def open_logs(self):
        if self._log_window is None or not _qt_alive(self._log_window):
            window = LogWindow()
            window.destroyed.connect(
                lambda *_args, w=window: self._on_log_window_destroyed(w)
            )
            self._log_window = window
        self._log_window.show()
        self._log_window.raise_()
        self._log_window.activateWindow()
        self._log_window.refresh()

    def _on_log_window_destroyed(self, window) -> None:
        if self._log_window is window or not _qt_alive(self._log_window):
            self._log_window = None

    def _clear_settings_window(self):
        if self.sender() is self._settings_window or not _qt_alive(self._settings_window):
            self._settings_window = None

    def _on_settings_saved(self):
        self._config_mtime = self._config_mtime_value()
        self._apply_hotkeys_from_config()
        self._sync_selection_bubble()
        set_start_on_boot(bool(self._config.get("start_on_boot", False)))
        logger.info(
            "设置已保存 | 划词=%s OCR=%s 划词按钮=%s 开机自启=%s",
            self._config.get("hotkey"),
            self._config.get("ocr_hotkey"),
            bool(self._config.get("selection_bubble", False)),
            bool(self._config.get("start_on_boot", False)),
        )

    def _on_bubble_translate(self, text: str, anchor: object):
        # 结果页出现在快捷按钮位置旁（与 OCR 相同的 cursor 定位）
        if isinstance(anchor, (tuple, list)) and len(anchor) >= 2:
            placement = (int(anchor[0]), int(anchor[1]))
        else:
            placement = cursor_physical_pos()
        self.open_translation_with_text(
            text,
            placement_physical=placement,
            placement_mode="cursor",
        )

    def _translation_hwnd(self) -> int | None:
        w = self._translation_window
        if not _qt_alive(w):
            self._translation_window = None
            return None
        try:
            return int(w.winId())
        except Exception:
            return None

    def _prepare_translation_window(
        self,
        *,
        placement_physical: tuple[int, int],
        placement_mode: str = "cursor",
        pending_selection: bool,
    ) -> TranslationWindow:
        """复用同一翻译窗；关闭后若 C++ 对象已销毁则重建。"""
        window = self._translation_window
        if window is not None and not _qt_alive(window):
            self._translation_window = None
            window = None

        if window is None:
            window = TranslationWindow(
                pending_selection=pending_selection,
                placement_physical=placement_physical,
                placement_mode=placement_mode,
            )
            # destroyed 的 sender 在部分环境下不可靠，用弱引用比对
            window.destroyed.connect(
                lambda *_args, w=window: self._on_translation_window_destroyed(w)
            )
            self._translation_window = window
        else:
            try:
                window.panel.shutdown_tasks()
            except RuntimeError:
                self._translation_window = None
                return self._prepare_translation_window(
                    placement_physical=placement_physical,
                    placement_mode=placement_mode,
                    pending_selection=pending_selection,
                )
            if pending_selection:
                window.panel.show_capturing()
            px, py = placement_physical
            place_window_near_physical(window, px, py, mode=placement_mode)
        return window

    def _on_translation_window_destroyed(self, window) -> None:
        if self._translation_window is window or not _qt_alive(self._translation_window):
            self._translation_window = None

    def open_translation(self):
        """划词快捷键：复用翻译窗、不抢焦点抓选区，完成后再激活。"""
        if ScreenshotSelector.is_active():
            return
        self._bubble_watcher.suppress_for(2.0)
        logger.info("划词快捷键触发")

        if self._selection_task is not None and self._selection_task.isRunning():
            self._selection_task.requestInterruption()
            self._selection_task.wait(2500)

        our_hwnd = self._translation_hwnd()
        target_hwnd = foreground_hwnd()
        if target_hwnd and our_hwnd and target_hwnd == our_hwnd:
            # 焦点还在翻译窗上时，不要对着自己 Ctrl+C
            target_hwnd = None

        placement = cursor_physical_pos()
        self._selection_token += 1
        token = self._selection_token

        window = self._prepare_translation_window(
            placement_physical=placement,
            placement_mode="cursor",
            pending_selection=True,
        )
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        window.show()

        if target_hwnd:
            force_foreground(target_hwnd)

        self._start_selection_capture(target_hwnd, token)

    def open_translation_with_text(
        self,
        text: str,
        *,
        placement_physical: tuple[int, int] | None = None,
        placement_mode: str = "cursor",
    ):
        """划词浮动按钮：直接用已选中的文本打开翻译界面。"""
        if ScreenshotSelector.is_active():
            return
        text = (text or "").strip()
        if not text:
            return
        logger.info("划词按钮翻译 | 长度=%d", len(text))
        log_captured_content("划词按钮", text, method="bubble")

        # 浮动按钮已有文本，取消进行中的快捷键抓取，避免稍后覆盖
        self._selection_token += 1
        if self._selection_task is not None and self._selection_task.isRunning():
            self._selection_task.requestInterruption()

        if placement_physical is None:
            placement_physical = cursor_physical_pos()
            placement_mode = "cursor"

        window = self._prepare_translation_window(
            placement_physical=placement_physical,
            placement_mode=placement_mode,
            pending_selection=False,
        )
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        window.show()
        window.raise_()
        window.activateWindow()
        window.apply_selection_text(text)

    def _start_selection_capture(self, prefer_hwnd: int | None, token: int):
        task = SelectionCaptureTask(prefer_hwnd, self)
        task.result_ready.connect(
            lambda text, t=token: self._on_selection_captured(text, t)
        )
        task.failed.connect(
            lambda message, t=token: self._on_selection_failed(message, t)
        )
        task.finished.connect(self._clear_selection_task)
        self._selection_task = task
        task.start()

    def _on_selection_captured(self, text: str, token: int):
        if token != self._selection_token:
            return
        window = self._translation_window
        if window is None:
            return
        if text:
            logger.info("选区捕获成功 | 长度=%d", len(text))
            window.apply_selection_text(text)
        else:
            logger.warning("选区捕获为空")
            window.apply_selection_empty()
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        window.raise_()
        window.activateWindow()

    def _on_selection_failed(self, message: str, token: int):
        if token != self._selection_token:
            return
        logger.error("选区捕获失败: %s", message)
        window = self._translation_window
        if window is not None:
            window.apply_ocr_error(message)
            window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
            window.raise_()
            window.activateWindow()
        else:
            self._tray.showMessage(
                "划词翻译",
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )

    def _clear_selection_task(self):
        task = self.sender()
        if task is self._selection_task:
            self._selection_task = None

    def start_ocr_capture(self):
        """OCR 快捷键：框选屏幕区域后识别并翻译。"""
        if ScreenshotSelector.is_active():
            return
        self._bubble_watcher.suppress_for(2.0)
        logger.info("OCR 快捷键触发")
        if not HAS_OCR:
            logger.error("OCR 不可用: %s", OCR_IMPORT_ERROR)
            self._tray.showMessage(
                "划词翻译",
                OCR_IMPORT_ERROR or "请安装 rapidocr-onnxruntime 后重试。",
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )
            return
        ScreenshotSelector.capture(self._on_screenshot_finished)

    def _on_screenshot_finished(self, pixmap, anchor=None):
        self._bubble_watcher.suppress_for(1.5)
        if pixmap is None or pixmap.isNull():
            logger.info("OCR 截图取消")
            return
        logger.info(
            "OCR 截图完成 | %dx%d",
            pixmap.width(),
            pixmap.height(),
        )
        if self._ocr_task is not None and self._ocr_task.isRunning():
            self._ocr_task.requestInterruption()
            self._ocr_task.wait(2000)

        if anchor is None or not isinstance(anchor, (tuple, list)) or len(anchor) < 2:
            anchor = cursor_physical_pos()
        else:
            anchor = (int(anchor[0]), int(anchor[1]))

        self._ocr_token += 1
        token = self._ocr_token

        old = self._ocr_window
        self._ocr_window = None
        if old is not None and _qt_alive(old):
            try:
                old.destroyed.disconnect(self._on_ocr_window_destroyed)
            except Exception:
                pass
            try:
                old.close()
            except RuntimeError:
                pass

        window = OCRWindow(
            screenshot=pixmap,
            pending_ocr=True,
            placement_physical=anchor,
        )
        window.destroyed.connect(
            lambda *_args, w=window: self._on_ocr_window_destroyed(w)
        )
        self._ocr_window = window
        window.show()
        window.raise_()
        window.activateWindow()
        self._start_ocr_task(pixmap, token)

    def _start_ocr_task(self, pixmap, token: int):
        task = OcrTask(pixmap, self)
        task.result_ready.connect(lambda text, t=token: self._on_ocr_result(text, t))
        task.failed.connect(lambda message, t=token: self._on_ocr_failed(message, t))
        task.finished.connect(self._clear_ocr_task)
        self._ocr_task = task
        task.start()

    def _on_ocr_result(self, text: str, token: int):
        if token != self._ocr_token:
            return
        window = self._ocr_window
        if not _qt_alive(window):
            self._ocr_window = None
            return
        logger.info("OCR 识别成功 | 长度=%d", len(text or ""))
        log_captured_content("OCR 识别", text or "", method="ocr")
        window.apply_recognized_text(text)

    def _on_ocr_failed(self, message: str, token: int):
        if token != self._ocr_token:
            return
        logger.error("OCR 识别失败: %s", message)
        window = self._ocr_window
        if _qt_alive(window):
            window.apply_ocr_error(message)
        else:
            self._ocr_window = None
            self._tray.showMessage(
                "划词翻译",
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )

    def _clear_ocr_task(self):
        task = self.sender()
        if task is self._ocr_task:
            self._ocr_task = None

    def _on_ocr_window_destroyed(self, window) -> None:
        if self._ocr_window is window or not _qt_alive(self._ocr_window):
            self._ocr_window = None

    def quit(self):
        logger.info("应用退出")
        if self._selection_task is not None and self._selection_task.isRunning():
            self._selection_task.requestInterruption()
            self._selection_task.wait(2000)
        if self._ocr_task is not None and self._ocr_task.isRunning():
            self._ocr_task.requestInterruption()
            self._ocr_task.wait(2000)
        self._bubble_watcher.shutdown()
        self._hotkeys.stop()
        self._tray.hide()
        self._app.quit()


def run_app() -> int:
    setup_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("划词翻译")
    qt_app.setQuitOnLastWindowClosed(False)
    qt_app.setFont(QFont("Microsoft YaHei UI", FONT_SIZE))
    qt_app.setWindowIcon(load_app_icon())

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("系统托盘不可用，无法启动后台应用。")
        print("系统托盘不可用，无法启动后台应用。")
        return 1

    SelectionTranslationApp(qt_app)
    return qt_app.exec()
