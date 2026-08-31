"""应用配置：快捷键与其它设置持久化。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from ui.constants import (
    DEFAULT_OCR_HEIGHT,
    DEFAULT_OCR_WIDTH,
    DEFAULT_TRANSLATION_HEIGHT,
    DEFAULT_TRANSLATION_WIDTH,
)

DEFAULT_HOTKEY = "Ctrl+Alt+T"
DEFAULT_OCR_HOTKEY = "Ctrl+Alt+O"
DEFAULT_SPLIT_RATIO = 0.5
DEFAULT_ENGINE = "自动选择"
DEFAULT_SOURCE_LANG = "自动检测"
DEFAULT_TARGET_LANG = "英语"

DEFAULT_CONFIG = {
    "hotkey": DEFAULT_HOTKEY,
    "ocr_hotkey": DEFAULT_OCR_HOTKEY,
    "start_on_boot": False,
    "selection_bubble": False,
    "window_pinned": False,
    "split_ratio": DEFAULT_SPLIT_RATIO,
    "translation_width": DEFAULT_TRANSLATION_WIDTH,
    "translation_height": DEFAULT_TRANSLATION_HEIGHT,
    "ocr_width": DEFAULT_OCR_WIDTH,
    "ocr_height": DEFAULT_OCR_HEIGHT,
    "engine": DEFAULT_ENGINE,
    "source_lang": DEFAULT_SOURCE_LANG,
    "target_lang": DEFAULT_TARGET_LANG,
}

SETTINGS_LOCK = "settings_editing.lock"


def is_frozen() -> bool:
    """PyInstaller / 其它打包运行时为 True。"""
    return bool(getattr(sys, "frozen", False))


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _dir_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("1", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def app_data_dir() -> Path:
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        config_in_exe = exe_dir / "settings_config.json"
        if config_in_exe.is_file() or _dir_is_writable(exe_dir):
            return exe_dir
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        data = local / "SelectionTranslation"
        data.mkdir(parents=True, exist_ok=True)
        return data
    return _project_root()


APP_DIR = app_data_dir()
CONFIG_FILE = APP_DIR / "settings_config.json"
SETTINGS_LOCK_FILE = APP_DIR / SETTINGS_LOCK


def normalize_hotkey(value: str) -> str:
    """全局热键只保留第一组按键序列。"""
    value = (value or "").strip()
    if not value:
        return ""
    return value.split(",")[0].strip()


def load_config() -> dict:
    try:
        # utf-8-sig：兼容安装器可能写入的 BOM
        raw = CONFIG_FILE.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError, TypeError):
        data = {}
    return {**DEFAULT_CONFIG, **data}


def save_config(config: dict) -> None:
    merged = {**DEFAULT_CONFIG, **config}
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def patch_config(**changes) -> dict:
    config = load_config()
    config.update(changes)
    save_config(config)
    return config

def acquire_settings_lock() -> None:
    try:
        SETTINGS_LOCK_FILE.write_text(f"{os.getpid()}\n", encoding="utf-8")
    except OSError:
        pass


def release_settings_lock() -> None:
    try:
        SETTINGS_LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def settings_lock_active() -> bool:
    """设置页录入快捷键期间为 True；进程已死或锁过期则自动清理。"""
    if not SETTINGS_LOCK_FILE.is_file():
        return False
    try:
        age = time.time() - SETTINGS_LOCK_FILE.stat().st_mtime
        raw = SETTINGS_LOCK_FILE.read_text(encoding="utf-8").strip().splitlines()
        pid = int(raw[0]) if raw and raw[0].isdigit() else None
    except (OSError, ValueError, TypeError):
        release_settings_lock()
        return False

    # 录入中途崩溃会留下锁文件，导致全局快捷键一直暂停
    if age > 600:
        release_settings_lock()
        return False
    if pid is not None and pid != os.getpid():
        try:
            os.kill(pid, 0)
        except OSError:
            release_settings_lock()
            return False
        # 其它进程的锁：本进程不认，避免误暂停
        return False
    return True
