"""Windows：隐藏第三方库拉起的控制台黑框（如 exejs 的 node/cscript）。"""

from __future__ import annotations

import sys


def suppress_console_windows() -> None:
    """给 subprocess.Popen 默认加上 CREATE_NO_WINDOW + SW_HIDE。"""
    if sys.platform != "win32":
        return

    import subprocess

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    startf_use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x1)
    sw_hide = 0

    original_init = subprocess.Popen.__init__

    def _init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        flags = kwargs.get("creationflags", 0) or 0
        kwargs["creationflags"] = int(flags) | create_no_window

        startupinfo = kwargs.get("startupinfo")
        if startupinfo is None:
            startupinfo = subprocess.STARTUPINFO()
            kwargs["startupinfo"] = startupinfo
        startupinfo.dwFlags |= startf_use_show_window
        startupinfo.wShowWindow = sw_hide

        return original_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _init  # type: ignore[method-assign]

    # asyncio 子进程（exejs 异步路径）同样隐藏窗口
    try:
        import asyncio

        original_exec = asyncio.create_subprocess_exec
        original_shell = asyncio.create_subprocess_shell

        async def _exec(*args, **kwargs):  # type: ignore[no-untyped-def]
            flags = kwargs.get("creationflags", 0) or 0
            kwargs["creationflags"] = int(flags) | create_no_window
            return await original_exec(*args, **kwargs)

        async def _shell(*args, **kwargs):  # type: ignore[no-untyped-def]
            flags = kwargs.get("creationflags", 0) or 0
            kwargs["creationflags"] = int(flags) | create_no_window
            return await original_shell(*args, **kwargs)

        asyncio.create_subprocess_exec = _exec  # type: ignore[assignment]
        asyncio.create_subprocess_shell = _shell  # type: ignore[assignment]
    except Exception:
        pass
