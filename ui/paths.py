"""默认文件对话框路径（桌面，避免落到安装目录）。"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog, QWidget


def desktop_dir() -> str:
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    if path:
        return path
    return str(Path.home() / "Desktop")


def desktop_path(filename: str = "") -> str:
    """打开/保存对话框的初始路径：桌面，或桌面上的建议文件名。

    仅目录时带尾部分隔符，避免 Windows 原生对话框把路径当成文件名。
    """
    base = desktop_dir()
    name = Path(str(filename).replace("\\", "/")).name if filename else ""
    if not name:
        if base.endswith(("/", "\\")):
            return base
        return base + (os.sep)
    return str(Path(base) / name)


def choose_open_file(
    parent: QWidget | None,
    title: str,
    file_filter: str,
    suggested: str = "",
) -> str:
    path, _ = QFileDialog.getOpenFileName(
        parent, title, desktop_path(suggested), file_filter
    )
    return path or ""


def choose_save_file(
    parent: QWidget | None,
    title: str,
    file_filter: str,
    suggested: str = "",
) -> str:
    path, _ = QFileDialog.getSaveFileName(
        parent, title, desktop_path(suggested), file_filter
    )
    return path or ""
