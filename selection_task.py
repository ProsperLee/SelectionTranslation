"""后台抓取选中文本。"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from app_log import log_captured_content
from selection import get_selected_text

logger = logging.getLogger("selection")


class SelectionCaptureTask(QThread):
    result_ready = Signal(str)
    failed = Signal(str)

    def __init__(self, prefer_hwnd: int | None = None, parent=None):
        super().__init__(parent)
        self._prefer_hwnd = prefer_hwnd

    def run(self):
        try:
            text, method = get_selected_text(prefer_hwnd=self._prefer_hwnd)
            text = (text or "").strip()
            if text:
                log_captured_content("划词选区", text, method=method)
            else:
                logger.warning("抓取为空 | 方式=%s hwnd=%s", method, self._prefer_hwnd)
        except Exception as exc:
            logger.exception("抓取异常: %s", exc)
            if not self.isInterruptionRequested():
                self.failed.emit(f"获取选中文本失败：{exc}")
            return
        if self.isInterruptionRequested():
            return
        self.result_ready.emit(text)
