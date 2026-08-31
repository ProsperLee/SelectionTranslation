"""便签浅色配色：全色相随机，不限色板；仅约束为浅色。"""

from __future__ import annotations

import colorsys
import random

from PySide6.QtGui import QColor

# 相对亮度下限（sRGB）：高于此视为浅色，可覆盖更鲜艳的高明度色
_MIN_RELATIVE_LUMINANCE = 0.48


def _hsl_to_qcolor(h: float, s: float, lightness: float) -> QColor:
    r, g, b = colorsys.hls_to_rgb(h, lightness, s)
    return QColor(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def _relative_luminance(color: QColor) -> float:
    def lin(c: int) -> float:
        x = c / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = lin(color.red()), lin(color.green()), lin(color.blue())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _is_light(color: QColor) -> bool:
    return _relative_luminance(color) >= _MIN_RELATIVE_LUMINANCE


def _color_distance(a: QColor, b: QColor) -> float:
    return (
        (a.red() - b.red()) ** 2
        + (a.green() - b.green()) ** 2
        + (a.blue() - b.blue()) ** 2
    ) ** 0.5


def _random_light_base() -> tuple[float, float, float]:
    """全色相 + 宽饱和度，用高明度保证仍是浅色。"""
    h = random.random()
    # 全饱和度范围；高饱和时靠更高明度压成浅色
    s = random.random()  # 0 ~ 1
    if s < 0.35:
        lightness = 0.72 + random.random() * 0.22  # 低饱和：灰粉到柔和浅色
    elif s < 0.70:
        lightness = 0.76 + random.random() * 0.18
    else:
        lightness = 0.82 + random.random() * 0.14  # 高饱和：必须更亮才浅
    return h, s, lightness


def random_note_colors(
    *,
    avoid_content: QColor | None = None,
) -> tuple[QColor, QColor]:
    """
    返回 (content, header) 浅色对。

    - 色相 / 饱和度全范围随机（全色域）
    - 仅用相对亮度约束为浅色
    - header 与 content 同色相、明度略有差异
    """
    for _ in range(64):
        h, s, content_l = _random_light_base()
        delta = 0.025 + random.random() * 0.07
        if random.random() < 0.65:
            header_l = min(0.97, content_l + delta)
        else:
            header_l = max(0.68, content_l - delta)
        if abs(header_l - content_l) < 0.02:
            header_l = min(0.97, content_l + 0.035)

        content = _hsl_to_qcolor(h, s, content_l)
        header = _hsl_to_qcolor(h, s, header_l)
        if not _is_light(content) or not _is_light(header):
            continue
        if content.name() == header.name():
            continue
        if avoid_content is not None and _color_distance(content, avoid_content) < 35:
            continue
        return content, header

    # 兜底：高明度全色相随机，仍不走固定色
    h = random.random()
    s = 0.35 + random.random() * 0.45
    content = _hsl_to_qcolor(h, s, 0.88)
    header = _hsl_to_qcolor(h, s, 0.93)
    return content, header
