"""防止重复启动主程序。"""

from __future__ import annotations

import sys

_MUTEX = None
_MUTEX_NAME = "Global\\SelectionTranslation.SingleInstance"


def acquire_single_instance() -> bool:
    """成功返回 True；已有实例时提示并返回 False。"""
    global _MUTEX
    if sys.platform != "win32":
        return True

    import ctypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    _MUTEX = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        user32.MessageBoxW(0, "划词翻译已在运行中。", "划词翻译", 0x40)
        if _MUTEX:
            kernel32.CloseHandle(_MUTEX)
            _MUTEX = None
        return False
    return True
