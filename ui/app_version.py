"""应用版本号（开发态读 packaging/version.txt；打包后读捆绑文件）。"""

from __future__ import annotations

import sys
from pathlib import Path


def get_app_version() -> str:
    rel = Path("packaging") / "version.txt"
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / rel)
        candidates.append(Path(sys.executable).resolve().parent / rel)
    candidates.append(Path(__file__).resolve().parent.parent / rel)
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "unknown"
