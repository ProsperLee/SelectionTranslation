"""截图文字识别（RapidOCR，输入为 QPixmap）。"""

from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap

try:
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    HAS_OCR = True
    OCR_IMPORT_ERROR = ""
except ImportError as exc:
    np = None  # type: ignore[assignment]
    RapidOCR = None  # type: ignore[misc, assignment]
    HAS_OCR = False
    OCR_IMPORT_ERROR = str(exc)

_ocr_engine = None


def pixmap_to_ndarray(pixmap: QPixmap):
    if np is None:
        raise RuntimeError(f"OCR 依赖不可用：{OCR_IMPORT_ERROR or '请安装 numpy 与 rapidocr-onnxruntime'}")

    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        raise ValueError("截图尺寸无效")

    bytes_per_line = image.bytesPerLine()
    buffer = image.constBits()
    if buffer is None:
        raise ValueError("无法读取截图数据")

    buffer_size = bytes_per_line * height
    array = np.frombuffer(buffer, dtype=np.uint8, count=buffer_size).reshape((height, bytes_per_line))
    rgb = array[:, : width * 3].reshape((height, width, 3))
    return np.ascontiguousarray(rgb)


def ocr_pixmap(pixmap: QPixmap) -> str:
    global _ocr_engine
    if not HAS_OCR:
        raise RuntimeError(f"OCR 依赖不可用：{OCR_IMPORT_ERROR or '请安装 rapidocr-onnxruntime'}")
    if pixmap.isNull():
        raise ValueError("截图为空")

    if _ocr_engine is None:
        _ocr_engine = RapidOCR()

    result, _ = _ocr_engine(pixmap_to_ndarray(pixmap))
    if not result:
        return ""
    return "\n".join(item[1] for item in result if len(item) > 1 and item[1]).strip()
