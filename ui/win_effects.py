import sys


def apply_acrylic_blur(hwnd: int, tint: tuple[int, int, int, int] = (20, 20, 24, 145)) -> bool:
    """Windows 毛玻璃（Acrylic）效果；失败时由调用方自行绘制半透明背景。"""
    if sys.platform != "win32" or hwnd <= 0:
        return False

    try:
        import ctypes

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_int),
                ("AnimationId", ctypes.c_int),
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.POINTER(ACCENT_POLICY)),
                ("SizeOfData", ctypes.c_size_t),
            ]

        accent_state = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        attribute = 19  # WCA_ACCENT_POLICY
        red, green, blue, alpha = tint
        gradient_color = (alpha << 24) | (blue << 16) | (green << 8) | red

        policy = ACCENT_POLICY(accent_state, 0, gradient_color, 0)
        data = WINDOWCOMPOSITIONATTRIBDATA(
            attribute,
            ctypes.pointer(policy),
            ctypes.sizeof(policy),
        )
        set_window_composition_attribute = ctypes.windll.user32.SetWindowCompositionAttribute
        return bool(set_window_composition_attribute(hwnd, ctypes.byref(data)))
    except Exception:
        return False


def set_window_topmost(hwnd: int, enabled: bool) -> bool:
    """仅调整 native Z 序，不修改 Qt windowFlags，避免闪烁或尺寸异常。"""
    if sys.platform != "win32" or hwnd <= 0:
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL

        swp_nomove = 0x0002
        swp_nosize = 0x0001
        swp_noactivate = 0x0010
        swp_showwindow = 0x0040
        flags = swp_nomove | swp_nosize | swp_noactivate | swp_showwindow

        window = wintypes.HWND(hwnd)
        insert_after = wintypes.HWND(-1 if enabled else -2)
        if not user32.SetWindowPos(window, insert_after, 0, 0, 0, 0, flags):
            return False

        if not enabled:
            user32.SetWindowPos(window, wintypes.HWND(0), 0, 0, 0, 0, flags)
        return True
    except Exception:
        return False
