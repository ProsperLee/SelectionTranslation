"""程序入口：DPI 初始化、单实例、托盘主循环 / 独立设置窗。"""

import sys


def _ensure_win_dpi_awareness_v2() -> None:
    """在 Qt 初始化前设置 DPI 感知，避免 qt.qpa.window 拒绝访问警告。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        if not hasattr(user32, "SetProcessDpiAwarenessContext"):
            return
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == (HANDLE)-4
        context = ctypes.c_void_p(-4)
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext(context)
    except Exception:
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            pass


def _ensure_win_app_user_model_id() -> None:
    """独立 AppID，避免任务栏沿用 python.exe 默认图标。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "SelectionTranslation.App"
        )
    except Exception:
        pass


_ensure_win_dpi_awareness_v2()
_ensure_win_app_user_model_id()

from PySide6.QtWidgets import QApplication

from app import run_app
from single_instance import acquire_single_instance


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--settings":
        from PySide6.QtGui import QFont
        from ui.constants import FONT_SIZE
        from ui.icons import load_app_icon
        from ui.settings_window import SettingsWindow

        app = QApplication(sys.argv)
        app.setApplicationName("划词翻译")
        app.setWindowIcon(load_app_icon())
        app.setFont(QFont("Microsoft YaHei UI", FONT_SIZE))
        window = SettingsWindow()
        window.setWindowIcon(app.windowIcon())
        window.show()
        sys.exit(app.exec())
        return

    if not acquire_single_instance():
        return 1

    sys.exit(run_app())


if __name__ == "__main__":
    main()
