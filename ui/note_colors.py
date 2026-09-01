"""便签配色：RGB 各通道 0–255 随机；透明度由窗口 NOTE_WINDOW_ALPHA 统一控制。"""

from __future__ import annotations

import random

from PySide6.QtGui import QColor

# ITU-R BT.601 感知亮度阈值：低于此视为深色底
_LUMA_DARK_THRESHOLD = 128.0


def is_dark_color(color: QColor) -> bool:
    """判断背景偏深（宜用白字）还是偏浅（宜用黑字）。"""
    luma = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return luma < _LUMA_DARK_THRESHOLD


def contrast_text_color(bg: QColor) -> QColor:
    """深色底 → 白字；浅色底 → 黑字。"""
    return QColor(255, 255, 255) if is_dark_color(bg) else QColor(51, 51, 51)


def _rand_rgb() -> QColor:
    return QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def _clamp(v: int) -> int:
    return max(0, min(255, v))


def _near_rgb(base: QColor) -> QColor:
    """同色附近微调，保证 header 与 content 近似但不相同。"""
    for _ in range(16):
        delta = random.randint(12, 40) * (1 if random.random() < 0.5 else -1)
        color = QColor(
            _clamp(base.red() + delta),
            _clamp(base.green() + delta),
            _clamp(base.blue() + delta),
        )
        if color.name() != base.name():
            return color
    # 兜底：固定偏移
    return QColor(
        _clamp(base.red() + 24),
        _clamp(base.green() + 24),
        _clamp(base.blue() + 24),
    )


def random_note_colors(
    *,
    avoid_content: QColor | None = None,
) -> tuple[QColor, QColor]:
    """
    返回 (content, header)。

    - RGB 全范围随机（0–255）
    - 颜色本身不设 Alpha（A 由窗口绘制时的 NOTE_WINDOW_ALPHA 决定）
    - header 为 content 附近色，近似但不相同
    """
    for _ in range(32):
        content = _rand_rgb()
        if avoid_content is not None and content.name() == avoid_content.name():
            continue
        header = _near_rgb(content)
        return content, header

    content = _rand_rgb()
    return content, _near_rgb(content)
