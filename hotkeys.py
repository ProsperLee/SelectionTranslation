"""全局快捷键注册（keyboard 库，回调通过 Qt 信号回到主线程）。"""

from __future__ import annotations

import logging
import re
import time

from PySide6.QtCore import QObject, Signal

from config import DEFAULT_HOTKEY, DEFAULT_OCR_HOTKEY, normalize_hotkey

try:
    import keyboard

    HAS_KEYBOARD = True
except ImportError:
    keyboard = None  # type: ignore[assignment]
    HAS_KEYBOARD = False

logger = logging.getLogger("hotkeys")

_MODIFIER_MAP = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "meta": "windows",
    "win": "windows",
    "super": "windows",
}


def qt_hotkey_to_keyboard(value: str) -> str:
    """QKeySequence 文本 -> keyboard 库格式。"""
    value = normalize_hotkey(value)
    if not value:
        return ""
    parts = [part.strip() for part in re.split(r"\s*\+\s*", value) if part.strip()]
    mapped: list[str] = []
    for part in parts:
        key = _MODIFIER_MAP.get(part.casefold(), part.lower())
        mapped.append(key)
    return "+".join(mapped)


class HotkeyManager(QObject):
    translation_triggered = Signal()
    ocr_triggered = Signal()
    registration_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._translation_hotkey = qt_hotkey_to_keyboard(DEFAULT_HOTKEY)
        self._ocr_hotkey = qt_hotkey_to_keyboard(DEFAULT_OCR_HOTKEY)
        self._translation_handle = None
        self._ocr_handle = None
        self._paused = False
        self._last_translation_at = 0.0
        self._last_ocr_at = 0.0
        self._debounce_s = 0.4

    def set_hotkeys(self, translation: str, ocr: str) -> None:
        self._translation_hotkey = qt_hotkey_to_keyboard(translation)
        self._ocr_hotkey = qt_hotkey_to_keyboard(ocr)
        if not self._paused:
            self._register_all()

    def is_paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        if paused == self._paused:
            return
        self._paused = paused
        if paused:
            self._unregister_all()
        else:
            self._register_all()

    def start(self) -> None:
        if not HAS_KEYBOARD:
            self.registration_failed.emit("未安装 keyboard 库，全局快捷键不可用。")
            return
        if not self._paused:
            self._register_all()

    def stop(self) -> None:
        self._unregister_all()
        if HAS_KEYBOARD:
            try:
                keyboard.unhook_all()
            except Exception:
                pass

    def _register_all(self) -> None:
        if not HAS_KEYBOARD:
            return
        self._unregister_all()
        try:
            if self._translation_hotkey:
                self._translation_handle = keyboard.add_hotkey(
                    self._translation_hotkey,
                    self._emit_translation,
                )
            if self._ocr_hotkey and self._ocr_hotkey != self._translation_hotkey:
                self._ocr_handle = keyboard.add_hotkey(
                    self._ocr_hotkey,
                    self._emit_ocr,
                )
            logger.info(
                "快捷键已注册 | 划词=%s OCR=%s",
                self._translation_hotkey,
                self._ocr_hotkey,
            )
        except Exception as exc:
            logger.exception("快捷键注册失败: %s", exc)
            self.registration_failed.emit(f"快捷键注册失败：{exc}")

    def _unregister_all(self) -> None:
        if not HAS_KEYBOARD:
            return
        for handle in (self._translation_handle, self._ocr_handle):
            if handle is None:
                continue
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._translation_handle = None
        self._ocr_handle = None

    def _emit_translation(self) -> None:
        if self._paused:
            return
        now = time.monotonic()
        if now - self._last_translation_at < self._debounce_s:
            return
        self._last_translation_at = now
        self.translation_triggered.emit()

    def _emit_ocr(self) -> None:
        if self._paused:
            return
        now = time.monotonic()
        if now - self._last_ocr_at < self._debounce_s:
            return
        self._last_ocr_at = now
        self.ocr_triggered.emit()
