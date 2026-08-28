"""
划词浮动按钮：轮询左键松手（不用全局钩子）。

流程：拖选 / 双击松手 → 延迟探测选区 → 在选区末尾显示按钮 → 点击打开翻译窗。
OCR / 快捷键翻译期间可通过 suppress_for / is_blocked 临时屏蔽。
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from PySide6.QtCore import QObject, QTimer, Signal
from typing import Callable

from selection import peek_selection as default_peek_selection
from ui.selection_bubble import SelectionBubble

VK_LBUTTON = 0x01
POLL_MS = 40
DRAG_THRESHOLD_PX = 6
DOUBLE_CLICK_MS = 450
MAX_SELECTION_CHARS = 8000
PEEK_DELAY_S = 0.04
AUTO_HIDE_MS = 5000

if sys.platform == "win32":
    user32 = ctypes.windll.user32
else:
    user32 = None


def _cursor_pos() -> tuple[int, int]:
    if user32 is None:
        return 0, 0
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _lbutton_down() -> bool:
    if user32 is None:
        return False
    return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)


class SelectionBubbleWatcher(QObject):
    translate_requested = Signal(str, object)
    _peek_ready = Signal(int, int, str, object, int)

    def __init__(
        self,
        parent=None,
        *,
        peek_selection: Callable[[], tuple[str, tuple[int, int] | None]] | None = None,
        is_blocked: Callable[[], bool] | None = None,
    ):
        super().__init__(parent)
        self._peek_selection = peek_selection or default_peek_selection
        self._is_blocked = is_blocked or (lambda: False)
        self._enabled = False
        self._bubble = SelectionBubble()
        self._bubble.clicked.connect(self._on_bubble_clicked)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(AUTO_HIDE_MS)
        self._hide_timer.timeout.connect(self._bubble.dismiss)
        self._peek_ready.connect(self._apply_peek_result)
        self._was_down = False
        self._down_pos: tuple[int, int] | None = None
        self._last_up_at = 0.0
        self._last_text = ""
        self._last_show_at = 0.0
        self._ignore_until = 0.0
        self._peek_gen = 0
        self._peek_lock = threading.Lock()

    def set_enabled(self, enabled: bool):
        enabled = bool(enabled) and sys.platform == "win32" and user32 is not None
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self._was_down = _lbutton_down()
            self._down_pos = _cursor_pos() if self._was_down else None
            self._poll_timer.start()
            return
        self._poll_timer.stop()
        self._hide_timer.stop()
        self._bubble.dismiss()

    def is_enabled(self) -> bool:
        return self._enabled

    def suppress_for(self, seconds: float = 1.0) -> None:
        self._ignore_until = max(self._ignore_until, time.time() + seconds)
        with self._peek_lock:
            self._peek_gen += 1
        self._hide_timer.stop()
        self._bubble.dismiss()

    def shutdown(self):
        self.set_enabled(False)
        self._bubble.dismiss()
        self._bubble.deleteLater()

    def _on_bubble_clicked(self):
        text = self._bubble.selection_text().strip()
        anchor = self._bubble.anchor_physical()
        self._ignore_until = time.time() + 0.8
        self._last_text = text
        self._hide_timer.stop()
        self._bubble.dismiss()
        if text:
            self.translate_requested.emit(text, anchor)

    def _poll(self):
        if not self._enabled:
            return
        try:
            down = _lbutton_down()
            x, y = _cursor_pos()
            if down and not self._was_down:
                self._down_pos = (x, y)
                if self._bubble.isVisible() and not self._bubble.contains_point(x, y):
                    self._hide_timer.stop()
                    self._bubble.dismiss()
            elif not down and self._was_down:
                self._handle_mouse_up(x, y)
            self._was_down = down
        except Exception:
            pass

    def _handle_mouse_up(self, x: int, y: int):
        if time.time() < self._ignore_until:
            return
        if self._is_blocked():
            return
        if self._bubble.contains_point(x, y):
            return

        down = self._down_pos
        self._down_pos = None
        now = time.time()
        dragged = False
        if down is not None:
            dragged = (
                abs(x - down[0]) >= DRAG_THRESHOLD_PX
                or abs(y - down[1]) >= DRAG_THRESHOLD_PX
            )
        double_click = (now - self._last_up_at) * 1000 <= DOUBLE_CLICK_MS
        self._last_up_at = now
        if not dragged and not double_click:
            return
        self._start_peek(x, y)

    def _start_peek(self, cursor_x: int, cursor_y: int):
        with self._peek_lock:
            self._peek_gen += 1
            gen = self._peek_gen

        def worker():
            time.sleep(PEEK_DELAY_S)
            if not self._enabled or gen != self._peek_gen:
                return
            if self._is_blocked():
                self._peek_ready.emit(cursor_x, cursor_y, "", None, gen)
                return
            text, anchor = "", None
            try:
                result = self._peek_selection(cursor_x, cursor_y)
                if isinstance(result, tuple):
                    text = (result[0] or "").strip()
                    anchor = result[1] if len(result) > 1 else None
                else:
                    text = (result or "").strip()
            except Exception:
                text, anchor = "", None
            if gen != self._peek_gen:
                return
            self._peek_ready.emit(cursor_x, cursor_y, text, anchor, gen)

        threading.Thread(target=worker, daemon=True, name="selection-bubble-peek").start()

    def _apply_peek_result(
        self,
        cursor_x: int,
        cursor_y: int,
        text: str,
        anchor: object,
        gen: int,
    ):
        if not self._enabled or gen != self._peek_gen:
            return
        if self._is_blocked():
            self._hide_timer.stop()
            self._bubble.dismiss()
            return
        if not text or len(text) > MAX_SELECTION_CHARS:
            return

        now = time.time()
        if (
            text == self._last_text
            and now - self._last_show_at < 1.0
            and self._bubble.isVisible()
        ):
            return

        if anchor and isinstance(anchor, (tuple, list)) and len(anchor) >= 2:
            bx, by = int(anchor[0]), int(anchor[1])
        else:
            bx, by = cursor_x + 8, cursor_y + 8

        self._last_text = text
        self._last_show_at = now
        self._bubble.popup_at(bx, by, text)
        self._hide_timer.start()
