"""开机自启（当前用户 Run 键）。"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

from config import APP_DIR, is_frozen, load_config, patch_config

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "SelectionTranslation"


def _pythonw_executable() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        return str(exe)
    candidate = exe.with_name("pythonw.exe")
    if candidate.is_file():
        return str(candidate)
    return str(exe)


def _startup_command() -> str:
    if is_frozen():
        return f'"{Path(sys.executable).resolve()}"'
    main_script = (APP_DIR / "main.py").resolve()
    return f'"{_pythonw_executable()}" "{main_script}"'


def is_start_on_boot_enabled() -> bool:
    """注册表中是否已存在开机自启项。"""
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, APP_REG_NAME)
            return True
    except OSError:
        return False


def set_start_on_boot(enabled: bool) -> None:
    """注册或移除当前用户的开机自启项。"""
    if sys.platform != "win32":
        return
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        if not enabled:
            try:
                winreg.DeleteValue(key, APP_REG_NAME)
            except FileNotFoundError:
                pass
            return
        winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, _startup_command())


def reconcile_start_on_boot() -> bool:
    """
    对齐「注册表自启」与「配置 start_on_boot」。

    安装包勾选开机自启时会先写注册表；若配置文件未写上或读失败，
    以前启动时会按配置 false 把注册表清掉，导致设置页勾选丢失。
    这里：注册表已开启则把配置同步为 true；否则以配置为准写回注册表。
    """
    reg_on = is_start_on_boot_enabled()
    config = load_config()
    cfg_on = bool(config.get("start_on_boot", False))

    if reg_on and not cfg_on:
        patch_config(start_on_boot=True)
        set_start_on_boot(True)  # 刷新为当前 exe 路径
        return True

    # 配置为真：确保注册表存在且指向当前可执行文件
    # 配置为假：移除注册表
    set_start_on_boot(cfg_on)
    return cfg_on
