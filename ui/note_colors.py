"""便签浅色配色：随机生成，header 与内容近似但不相等。"""

from __future__ import annotations

import colorsys
import random

from PySide6.QtGui import QColor


def _hsl_to_qcolor(h: float, s: float, lightness: float) -> QColor:
    r, g, b = colorsys.hls_to_rgb(h, lightness, s)
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def random_note_colors(
    *,
    avoid_content: QColor | None = None,
) -> tuple[QColor, QColor]:
    """
    返回 (content, header) 浅色对。

    - 均为高明度浅色
    - header 与 content 同色相、略有明度差（近似但不相同）
    """
    for _ in range(24):
        h = random.random()
        s = 0.28 + random.random() * 0.32
        content_l = 0.78 + random.random() * 0.10
        # header 略亮一点，保证肉眼可区分且整体近似
        delta = 0.035 + random.random() * 0.045
        header_l = min(0.96, content_l + delta)
        if abs(header_l - content_l) < 0.03:
            header_l = min(0.96, content_l + 0.04)

        content = _hsl_to_qcolor(h, s, content_l)
        header = _hsl_to_qcolor(h, s, header_l)
        if content == header:
            continue
        if avoid_content is not None and content.name() == avoid_content.name():
            continue
        return content, header

    # 兜底：固定浅粉
    return QColor("#F0B6F0"), QColor("#EFC1EF")
