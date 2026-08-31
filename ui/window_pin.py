"""窗口置顶公共逻辑（翻译窗 / 便签等共用）。"""

from __future__ import annotations

from typing import Protocol


class _PinnableWindow(Protocol):
    def set_stays_on_top(self, enabled: bool) -> None: ...


def apply_window_pin(window: _PinnableWindow, pinned: bool) -> bool:
    """
    设置窗口是否置顶。

    依赖窗口实现 ``set_stays_on_top``（如 FramelessWindow，内部走 Win32 Z 序）。
    返回最终置顶状态。
    """
    enabled = bool(pinned)
    window.set_stays_on_top(enabled)
    return enabled


def toggle_window_pin(window: _PinnableWindow, currently_pinned: bool) -> bool:
    """切换置顶，返回切换后的状态。"""
    return apply_window_pin(window, not currently_pinned)
