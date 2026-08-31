"""Win32 / UIA 物理屏幕坐标与 Qt 全局坐标互转（多屏 + 混合 DPI）。"""

from __future__ import annotations

import sys
from ctypes import wintypes

if sys.platform == "win32":
    import ctypes

    user32 = ctypes.windll.user32

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", _RECT),
            ("rcWork", _RECT),
            ("dwFlags", wintypes.DWORD),
        ]
else:
    user32 = None


def _monitor_from_point(x: int, y: int) -> int | None:
    if user32 is None:
        return None
    try:
        pt = wintypes.POINT(int(x), int(y))
        # MONITOR_DEFAULTTONEAREST
        handle = user32.MonitorFromPoint(pt, 2)
        return int(handle) if handle else None
    except Exception:
        return None


def _monitor_rect(handle: int) -> tuple[int, int, int, int] | None:
    if user32 is None:
        return None
    try:
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            return None
        rect = info.rcMonitor
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    except Exception:
        return None


def _screen_native_handle(screen) -> int | None:
    try:
        from PySide6.QtGui import QNativeInterface

        win_screen = QNativeInterface.QWindowsScreen(screen)
        if win_screen is not None:
            return int(win_screen.nativeHandle())
    except Exception:
        pass
    return None


def physical_global_to_qt(x: int, y: int) -> tuple[int, int]:
    """Win32 / UIA 物理桌面坐标 → Qt 全局逻辑坐标。"""
    if sys.platform != "win32":
        return int(x), int(y)

    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return int(x), int(y)

    handle = _monitor_from_point(x, y)
    if handle is None:
        return int(x), int(y)

    bounds = _monitor_rect(handle)
    if bounds is None:
        return int(x), int(y)

    left, top, _right, _bottom = bounds
    for screen in app.screens():
        if _screen_native_handle(screen) != handle:
            continue
        geo = screen.geometry()
        dpr = float(screen.devicePixelRatio()) or 1.0
        qx = geo.left() + (int(x) - left) / dpr
        qy = geo.top() + (int(y) - top) / dpr
        return int(qx), int(qy)

    return int(x), int(y)


def qt_global_to_physical(qx: int, qy: int) -> tuple[int, int]:
    """Qt 全局逻辑坐标 → Win32 物理桌面坐标。"""
    if sys.platform != "win32":
        return int(qx), int(qy)

    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return int(qx), int(qy)

    screen = app.screenAt(QPoint(int(qx), int(qy))) or app.primaryScreen()
    if screen is None:
        return int(qx), int(qy)

    handle = _screen_native_handle(screen)
    bounds = _monitor_rect(handle) if handle else None
    if bounds is None:
        return int(qx), int(qy)

    left, top, _right, _bottom = bounds
    geo = screen.geometry()
    dpr = float(screen.devicePixelRatio()) or 1.0
    px = left + (int(qx) - geo.left()) * dpr
    py = top + (int(qy) - geo.top()) * dpr
    return int(round(px)), int(round(py))


def qt_screen_at_physical(x: int, y: int):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return None

    qx, qy = physical_global_to_qt(x, y)
    return app.screenAt(QPoint(qx, qy))


def cursor_physical_pos() -> tuple[int, int]:
    if user32 is None:
        from PySide6.QtGui import QCursor

        pos = QCursor.pos()
        return int(pos.x()), int(pos.y())
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _work_area_at_qt(qx: int, qy: int):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return None
    screen = app.screenAt(QPoint(qx, qy)) or app.primaryScreen()
    if screen is None:
        return None
    return screen.availableGeometry()


def place_window_near_physical(
    widget,
    px: int,
    py: int,
    *,
    mode: str = "cursor",
) -> None:
    """
    将窗口贴近物理坐标锚点显示，边缘自动翻转。
    mode='cursor'：鼠标右下方；mode='selection'：选区后方（右侧优先，放不下则左侧）。
    不调用 adjustSize，避免冲掉已从配置恢复的宽高。
    """
    qx, qy = physical_global_to_qt(int(px), int(py))
    width = max(1, widget.width())
    height = max(1, widget.height())
    area = _work_area_at_qt(qx, qy)
    if area is None:
        widget.move(qx + 12, qy + 12)
        return

    margin = 8
    offset = 12
    left, top, right, bottom = area.left(), area.top(), area.right(), area.bottom()

    if mode == "selection":
        x = qx + offset
        y = qy - height // 2
        if x + width > right - margin:
            x = qx - width - offset
        if y + height > bottom - margin:
            y = bottom - height - margin
        if y < top + margin:
            y = top + margin
    else:
        x = qx + offset
        y = qy + offset
        if x + width > right - margin:
            x = qx - width - offset
        if y + height > bottom - margin:
            y = qy - height - offset

    x = min(max(left + margin, x), max(left + margin, right - width - margin))
    y = min(max(top + margin, y), max(top + margin, bottom - height - margin))
    widget.move(int(x), int(y))
