"""截图文字识别（RapidOCR，输入为 QPixmap）。"""

from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap

try:
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    HAS_OCR = True
    OCR_IMPORT_ERROR = ""
except ImportError as exc:
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    RapidOCR = None  # type: ignore[misc, assignment]
    HAS_OCR = False
    OCR_IMPORT_ERROR = str(exc)

_ocr_engine = None

# 小图放大到最短边，便于识别按钮/小字
_MIN_SIDE = 720
_MAX_SIDE = 2560


def pixmap_to_ndarray(pixmap: QPixmap):
    """QPixmap → BGR ndarray（RapidOCR 对 ndarray 按 OpenCV BGR 处理）。"""
    if np is None:
        raise RuntimeError(f"OCR 依赖不可用：{OCR_IMPORT_ERROR or '请安装 numpy 与 rapidocr-onnxruntime'}")

    # 深拷贝，避免 constBits 缓冲区在 Qt 侧失效
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888).copy()
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        raise ValueError("截图尺寸无效")

    bytes_per_line = image.bytesPerLine()
    buffer = image.constBits()
    if buffer is None:
        raise ValueError("无法读取截图数据")

    buffer_size = bytes_per_line * height
    array = np.frombuffer(buffer, dtype=np.uint8, count=buffer_size).reshape(
        (height, bytes_per_line)
    )
    rgb = array[:, : width * 3].reshape((height, width, 3))
    # ndarray 入口不会做 RGB→BGR，必须手动转
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    return bgr


def _upscale_for_ocr(img):
    """放大过小的截图，改善 UI 小字识别率。"""
    h, w = img.shape[:2]
    min_side = min(h, w)
    max_side = max(h, w)
    if min_side >= _MIN_SIDE:
        return img

    scale = _MIN_SIDE / max(min_side, 1)
    if max_side * scale > _MAX_SIDE:
        scale = _MAX_SIDE / max(max_side, 1)
    if scale <= 1.05:
        return img

    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def _enhance_contrast(img):
    """轻度对比度增强，利于深色界面上的浅色文字。"""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lightness = clahe.apply(lightness)
    return cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)


def _join_ocr_result(result) -> str:
    if not result:
        return ""
    return "\n".join(
        item[1] for item in result if len(item) > 1 and item[1]
    ).strip()


def ocr_pixmap(pixmap: QPixmap) -> str:
    global _ocr_engine
    if not HAS_OCR:
        raise RuntimeError(f"OCR 依赖不可用：{OCR_IMPORT_ERROR or '请安装 rapidocr-onnxruntime'}")
    if pixmap.isNull():
        raise ValueError("截图为空")

    if _ocr_engine is None:
        _ocr_engine = RapidOCR()

    img = _upscale_for_ocr(pixmap_to_ndarray(pixmap))

    # 先正常识别；失败再降低阈值并增强对比度重试（小按钮/浅色字）
    attempts = (
        {},
        {"box_thresh": 0.3, "text_score": 0.3, "unclip_ratio": 2.0},
    )
    text = ""
    for index, kwargs in enumerate(attempts):
        candidate = img if index == 0 else _enhance_contrast(img)
        result, _ = _ocr_engine(candidate, **kwargs)
        text = _join_ocr_result(result)
        if text:
            break
    return text
