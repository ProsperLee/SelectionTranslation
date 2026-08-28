"""后台 OCR 任务。"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap

from ocr import HAS_OCR, OCR_IMPORT_ERROR, ocr_pixmap


class OcrTask(QThread):
    result_ready = Signal(str)
    failed = Signal(str)

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap

    def run(self):
        if not HAS_OCR:
            self.failed.emit(
                f"OCR 依赖不可用：{OCR_IMPORT_ERROR or '请安装 rapidocr-onnxruntime'}"
            )
            return
        try:
            text = ocr_pixmap(self._pixmap)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(f"OCR 识别失败：{exc}")
            return
        if self.isInterruptionRequested():
            return
        if not text:
            self.failed.emit("未识别到文字，请框选包含清晰文字的区域。")
            return
        self.result_ready.emit(text)
