"""文本读音：有道 dictvoice（主）+ Windows 语音（兜底）。"""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("tts")

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
_MAX_CHARS = 280


def _prepare_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS].rstrip() + "…"
    return text


def _friendly_error(exc: BaseException) -> str:
    msg = str(exc) or exc.__class__.__name__
    low = msg.casefold()
    if "codec" in low or "encode" in low or "decode" in low:
        return "读音失败：文本编码异常，请稍后重试或缩短内容。"
    if isinstance(exc, urllib.error.URLError) or "urlopen" in low or "timed out" in low:
        return "读音失败：网络不可用，且系统语音也无法播放。"
    if "mci" in low:
        return f"读音失败：无法播放音频。\n{msg}"
    if len(msg) > 160:
        msg = msg[:160].rstrip() + "…"
    return f"读音失败：{msg}"


def _youdao_url(text: str) -> str:
    params: dict[str, str] = {"audio": text}
    if re.search(r"[\u4e00-\u9fff]", text):
        params["le"] = "zh"
    else:
        params["type"] = "2"  # 美音
    return "https://dict.youdao.com/dictvoice?" + urllib.parse.urlencode(params)


def _download_youdao_mp3(text: str, dest: Path) -> None:
    req = urllib.request.Request(_youdao_url(text), headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read()
    if not data or len(data) < 64:
        raise RuntimeError("读音数据为空")
    dest.write_bytes(data)


class _WinMciPlayer:
    """用 Windows MCI 异步播放本地 mp3（不依赖 QtMultimedia）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alias = "seltrans_tts"
        if sys.platform == "win32":
            self._winmm = __import__("ctypes").windll.winmm
        else:
            self._winmm = None

    def _mci(self, command: str) -> int:
        if self._winmm is None:
            return 1
        return int(self._winmm.mciSendStringW(command, None, 0, None))

    def stop(self) -> None:
        with self._lock:
            self._mci(f"stop {self._alias}")
            self._mci(f"close {self._alias}")

    def play_file(self, path: Path) -> None:
        if self._winmm is None:
            raise RuntimeError("当前系统不支持音频播放")
        path_str = str(path.resolve()).replace("'", r"\'")
        with self._lock:
            self._mci(f"stop {self._alias}")
            self._mci(f"close {self._alias}")
            err = self._mci(f'open "{path_str}" type mpegvideo alias {self._alias}')
            if err:
                err = self._mci(f'open "{path_str}" alias {self._alias}')
            if err:
                raise RuntimeError(f"无法打开音频 (MCI {err})")
            err = self._mci(f"play {self._alias}")
            if err:
                self._mci(f"close {self._alias}")
                raise RuntimeError(f"无法播放音频 (MCI {err})")


def _speak_sapi(text: str) -> None:
    """PowerShell System.Speech 离线兜底（UTF-8 临时文件，避免 gbk 编码错误）。"""
    if sys.platform != "win32":
        raise RuntimeError("不支持的系统")
    import subprocess

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    fd, name = tempfile.mkstemp(prefix="seltrans_tts_txt_", suffix=".txt")
    os.close(fd)
    txt_path = Path(name)
    try:
        txt_path.write_text(text, encoding="utf-8-sig")
        # 路径中的单引号对 PowerShell 字面量转义
        ps_path = str(txt_path.resolve()).replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate = 0; "
            f"$t = Get-Content -LiteralPath '{ps_path}' -Raw -Encoding UTF8; "
            "if ($t) { $s.Speak($t) }"
        )
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            timeout=60,
            creationflags=create_no_window,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or b"").decode(
                "utf-8", errors="replace"
            ).strip()
            raise RuntimeError(detail or "系统语音失败")
    finally:
        try:
            txt_path.unlink(missing_ok=True)
        except OSError:
            pass


class TtsPlayer(QObject):
    """单例式读音播放器：新请求会打断上一次。"""

    started = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = _WinMciPlayer()
        self._thread: threading.Thread | None = None
        self._gen = 0
        self._tmp_files: list[Path] = []

    def stop(self) -> None:
        self._gen += 1
        self._player.stop()

    def speak(self, text: str) -> None:
        prepared = _prepare_text(text)
        if not prepared:
            self.failed.emit("没有可朗读的文本")
            return
        self._gen += 1
        gen = self._gen
        self._player.stop()
        self.started.emit(prepared)

        def worker() -> None:
            tmp: Path | None = None
            try:
                fd, name = tempfile.mkstemp(prefix="seltrans_tts_", suffix=".mp3")
                os.close(fd)
                tmp = Path(name)
                self._tmp_files.append(tmp)
                try:
                    _download_youdao_mp3(prepared, tmp)
                    if gen != self._gen:
                        return
                    self._player.play_file(tmp)
                except Exception as online_exc:  # noqa: BLE001
                    logger.info("在线读音失败，改用系统语音: %s", online_exc)
                    if gen != self._gen:
                        return
                    _speak_sapi(prepared)
                if gen == self._gen:
                    self.finished.emit()
            except Exception as exc:  # noqa: BLE001
                logger.exception("读音失败")
                if gen == self._gen:
                    self.failed.emit(_friendly_error(exc))
            finally:
                self._cleanup_old_temps(keep=tmp)

        self._thread = threading.Thread(target=worker, daemon=True, name="tts-speak")
        self._thread.start()

    def _cleanup_old_temps(self, keep: Path | None) -> None:
        remain: list[Path] = []
        for path in self._tmp_files:
            if keep is not None and path == keep:
                remain.append(path)
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                remain.append(path)
        self._tmp_files = remain[-8:]


_shared: TtsPlayer | None = None


def shared_tts() -> TtsPlayer:
    global _shared
    if _shared is None:
        _shared = TtsPlayer()
    return _shared
