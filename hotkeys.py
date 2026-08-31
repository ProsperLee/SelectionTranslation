"""全局快捷键：Win32 RegisterHotKey（休眠/锁屏后仍可用）。"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from ctypes import wintypes

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget

from config import (
    DEFAULT_COLOR_PICKER_HOTKEY,
    DEFAULT_HOTKEY,
    DEFAULT_OCR_HOTKEY,
    normalize_hotkey,
)

logger = logging.getLogger("hotkeys")

WM_HOTKEY = 0x0312
WM_WTSSESSION_CHANGE = 0x02B1
WM_POWERBROADCAST = 0x0218
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5
NOTIFY_FOR_THIS_SESSION = 0
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ID_TRANSLATION = 1
HOTKEY_ID_OCR = 2
HOTKEY_ID_COLOR_PICKER = 3

_user32 = ctypes.windll.user32 if sys.platform == "win32" else None
_kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None

if sys.platform == "win32":
    _user32.RegisterHotKey.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        wintypes.UINT,
        wintypes.UINT,
    ]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
    try:
        _wts = ctypes.windll.wtsapi32
        _wts.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
        _wts.WTSRegisterSessionNotification.restype = wintypes.BOOL
        _wts.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]
        _wts.WTSUnRegisterSessionNotification.restype = wintypes.BOOL
    except Exception:  # noqa: BLE001
        _wts = None  # type: ignore[assignment]
else:
    _wts = None  # type: ignore[assignment]


_QT_KEY_TO_VK: dict[int, int] = {}
for _code in range(ord("0"), ord("9") + 1):
    _QT_KEY_TO_VK[_code] = _code
for _code in range(ord("A"), ord("Z") + 1):
    _QT_KEY_TO_VK[_code] = _code

_EXTRA_KEYS = {
    Qt.Key.Key_Space: 0x20,
    Qt.Key.Key_Escape: 0x1B,
    Qt.Key.Key_Tab: 0x09,
    Qt.Key.Key_Backspace: 0x08,
    Qt.Key.Key_Return: 0x0D,
    Qt.Key.Key_Enter: 0x0D,
    Qt.Key.Key_Insert: 0x2D,
    Qt.Key.Key_Delete: 0x2E,
    Qt.Key.Key_Home: 0x24,
    Qt.Key.Key_End: 0x23,
    Qt.Key.Key_PageUp: 0x21,
    Qt.Key.Key_PageDown: 0x22,
    Qt.Key.Key_Left: 0x25,
    Qt.Key.Key_Up: 0x26,
    Qt.Key.Key_Right: 0x27,
    Qt.Key.Key_Down: 0x28,
    Qt.Key.Key_CapsLock: 0x14,
    Qt.Key.Key_NumLock: 0x90,
    Qt.Key.Key_ScrollLock: 0x91,
    Qt.Key.Key_Pause: 0x13,
    Qt.Key.Key_Print: 0x2C,
    Qt.Key.Key_Plus: 0xBB,
    Qt.Key.Key_Minus: 0xBD,
    Qt.Key.Key_Equal: 0xBB,
    Qt.Key.Key_Comma: 0xBC,
    Qt.Key.Key_Period: 0xBE,
    Qt.Key.Key_Slash: 0xBF,
    Qt.Key.Key_Semicolon: 0xBA,
    Qt.Key.Key_Apostrophe: 0xDE,
    Qt.Key.Key_BracketLeft: 0xDB,
    Qt.Key.Key_BracketRight: 0xDD,
    Qt.Key.Key_Backslash: 0xDC,
    Qt.Key.Key_QuoteLeft: 0xC0,
    Qt.Key.Key_AsciiTilde: 0xC0,
}
for _k, _v in _EXTRA_KEYS.items():
    _QT_KEY_TO_VK[int(_k)] = _v
for _i in range(1, 25):
    _qt_f = getattr(Qt.Key, f"Key_F{_i}", None)
    if _qt_f is not None:
        _QT_KEY_TO_VK[int(_qt_f)] = 0x70 + (_i - 1)


def parse_hotkey(value: str) -> tuple[int, int] | None:
    """配置字符串 -> (modifiers, vk)；失败返回 None。"""
    value = normalize_hotkey(value)
    if not value:
        return None
    seq = QKeySequence(value)
    if seq.isEmpty():
        return None
    combo = seq[0]
    qt_mods = combo.keyboardModifiers()
    qt_key = combo.key()

    mods = MOD_NOREPEAT
    if qt_mods & Qt.KeyboardModifier.ControlModifier:
        mods |= MOD_CONTROL
    if qt_mods & Qt.KeyboardModifier.AltModifier:
        mods |= MOD_ALT
    if qt_mods & Qt.KeyboardModifier.ShiftModifier:
        mods |= MOD_SHIFT
    if qt_mods & Qt.KeyboardModifier.MetaModifier:
        mods |= MOD_WIN

    vk = _QT_KEY_TO_VK.get(int(qt_key))
    if vk is None:
        return None
    # 至少要有一个修饰键，避免劫持普通字母
    if mods == MOD_NOREPEAT:
        return None
    return mods, vk


class _HotkeySink(QWidget):
    """隐藏消息窗：接收 WM_HOTKEY / 会话解锁 / 休眠恢复。"""

    def __init__(self, manager: "HotkeyManager"):
        super().__init__()
        self._manager = manager
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.resize(1, 1)

    def nativeEvent(self, eventType, message):  # noqa: N802
        if sys.platform != "win32":
            return super().nativeEvent(eventType, message)
        et = bytes(eventType) if not isinstance(eventType, (bytes, bytearray)) else eventType
        if et not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return super().nativeEvent(eventType, message)
        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError, OverflowError):
            return super().nativeEvent(eventType, message)

        if msg.message == WM_HOTKEY:
            self._manager._on_win_hotkey(int(msg.wParam))
            return True, 0
        if msg.message == WM_WTSSESSION_CHANGE:
            if int(msg.wParam) in (WTS_SESSION_UNLOCK, WTS_SESSION_LOGON):
                self._manager._schedule_reregister("session-unlock")
        elif msg.message == WM_POWERBROADCAST:
            if int(msg.wParam) in (PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC):
                self._manager._schedule_reregister("power-resume")
        return super().nativeEvent(eventType, message)


class HotkeyManager(QObject):
    translation_triggered = Signal()
    ocr_triggered = Signal()
    color_picker_triggered = Signal()
    registration_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._translation_raw = normalize_hotkey(DEFAULT_HOTKEY)
        self._ocr_raw = normalize_hotkey(DEFAULT_OCR_HOTKEY)
        self._color_picker_raw = normalize_hotkey(DEFAULT_COLOR_PICKER_HOTKEY)
        self._paused = False
        self._started = False
        self._registered: set[int] = set()
        self._last_translation_at = 0.0
        self._last_ocr_at = 0.0
        self._last_color_picker_at = 0.0
        self._debounce_s = 0.4
        self._reregister_pending = False

        self._sink = _HotkeySink(self)
        self._sink.show()
        self._sink.hide()
        self._hwnd = int(self._sink.winId())

        self._session_notify = False
        if sys.platform == "win32" and _wts is not None:
            try:
                self._session_notify = bool(
                    _wts.WTSRegisterSessionNotification(self._hwnd, NOTIFY_FOR_THIS_SESSION)
                )
            except Exception:
                logger.exception("WTSRegisterSessionNotification 失败")

        # 兜底：长时间运行后偶发失效时定期重注册
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(5 * 60 * 1000)
        self._watchdog.timeout.connect(self._watchdog_reregister)

    def set_hotkeys(self, translation: str, ocr: str, color_picker: str) -> None:
        self._translation_raw = normalize_hotkey(translation)
        self._ocr_raw = normalize_hotkey(ocr)
        self._color_picker_raw = normalize_hotkey(color_picker)
        if self._started and not self._paused:
            self._register_all()

    def is_paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        if paused == self._paused:
            return
        self._paused = paused
        if not self._started:
            return
        if paused:
            self._unregister_all()
        else:
            self._register_all()

    def start(self) -> None:
        if sys.platform != "win32":
            self.registration_failed.emit("当前系统不支持全局快捷键。")
            return
        self._started = True
        if not self._paused:
            self._register_all()
        self._watchdog.start()

    def stop(self) -> None:
        self._watchdog.stop()
        self._unregister_all()
        self._started = False
        if self._session_notify and _wts is not None:
            try:
                _wts.WTSUnRegisterSessionNotification(self._hwnd)
            except Exception:
                pass
            self._session_notify = False

    def _schedule_reregister(self, reason: str) -> None:
        if self._reregister_pending or not self._started or self._paused:
            return
        self._reregister_pending = True
        logger.info("计划重新注册快捷键 | reason=%s", reason)
        QTimer.singleShot(800, self._do_reregister)

    def _do_reregister(self) -> None:
        self._reregister_pending = False
        if not self._started or self._paused:
            return
        self._register_all()

    def _watchdog_reregister(self) -> None:
        if self._started and not self._paused:
            self._register_all()

    def _register_all(self) -> None:
        if sys.platform != "win32" or _user32 is None:
            return
        self._unregister_all()
        errors: list[str] = []

        pairs = [
            (HOTKEY_ID_TRANSLATION, self._translation_raw, "划词"),
            (HOTKEY_ID_OCR, self._ocr_raw, "OCR"),
            (HOTKEY_ID_COLOR_PICKER, self._color_picker_raw, "吸色"),
        ]
        seen: set[tuple[int, int]] = set()
        for hotkey_id, raw, label in pairs:
            parsed = parse_hotkey(raw)
            if parsed is None:
                errors.append(f"{label}快捷键无效：{raw or '(空)'}")
                continue
            mods, vk = parsed
            if (mods, vk) in seen:
                continue
            seen.add((mods, vk))
            ok = bool(_user32.RegisterHotKey(self._hwnd, hotkey_id, mods, vk))
            if not ok:
                err = int(_kernel32.GetLastError()) if _kernel32 else 0
                msg = f"{label}快捷键注册失败（可能被占用）：{raw}"
                if err:
                    msg = f"{msg} (WinError {err})"
                errors.append(msg)
                logger.error(msg)
            else:
                self._registered.add(hotkey_id)

        logger.info(
            "快捷键已注册 | 划词=%s OCR=%s 吸色=%s ids=%s",
            self._translation_raw,
            self._ocr_raw,
            self._color_picker_raw,
            sorted(self._registered),
        )
        if errors and not self._registered:
            self.registration_failed.emit("；".join(errors))

    def _unregister_all(self) -> None:
        if sys.platform != "win32" or _user32 is None:
            self._registered.clear()
            return
        for hotkey_id in (
            HOTKEY_ID_TRANSLATION,
            HOTKEY_ID_OCR,
            HOTKEY_ID_COLOR_PICKER,
        ):
            try:
                _user32.UnregisterHotKey(self._hwnd, hotkey_id)
            except Exception:
                pass
        self._registered.clear()

    def _on_win_hotkey(self, hotkey_id: int) -> None:
        if self._paused:
            return
        now = time.monotonic()
        if hotkey_id == HOTKEY_ID_TRANSLATION:
            if now - self._last_translation_at < self._debounce_s:
                return
            self._last_translation_at = now
            self.translation_triggered.emit()
        elif hotkey_id == HOTKEY_ID_OCR:
            if now - self._last_ocr_at < self._debounce_s:
                return
            self._last_ocr_at = now
            self.ocr_triggered.emit()
        elif hotkey_id == HOTKEY_ID_COLOR_PICKER:
            if now - self._last_color_picker_at < self._debounce_s:
                return
            self._last_color_picker_at = now
            self.color_picker_triggered.emit()
