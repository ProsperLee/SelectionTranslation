"""进程内日志缓冲：彩色级别、完整时间戳、内容记录、定时清理。"""

from __future__ import annotations

import logging
import sys
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock

# 最多保留条数；超过则丢弃最旧
MAX_LINES = 3000
# 超过此时长（秒）的日志自动清除
MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7天
# 日志查看区字号（改这里即可；log_window 会引用此常量）
LOG_FONT_PX = 10
# 后台清理检查间隔（秒）
PURGE_INTERVAL_SECONDS = 10 * 60  # 10 分钟
# 内容日志：标题与正文分隔符（正文另起一行、带框显示）
CONTENT_SEP = "\n\x1fCONTENT\x1f\n"


@dataclass(frozen=True)
class LogEntry:
    timestamp: float
    level: int
    level_name: str
    name: str
    message: str

    def plain_line(self) -> str:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        header, body = split_content_message(self.message)
        if body is None:
            msg = _single_line(self.message)
            return f"{ts} [{self.level_name}] {self.name}: {msg}"
        return (
            f"{ts} [{self.level_name}] {self.name}: {_single_line(header)}\n"
            f"┌── 内容 ──\n{body}\n└────────"
        )


_buffer: deque[LogEntry] = deque(maxlen=MAX_LINES)
_lock = Lock()
_installed = False
_purge_callback = None  # optional Qt-side hook


class MemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(getattr(record, "msg", ""))
        entry = LogEntry(
            timestamp=record.created,
            level=record.levelno,
            level_name=record.levelname,
            name=record.name,
            message=msg,
        )
        with _lock:
            _buffer.append(entry)
            _purge_locked(now=record.created)


def _purge_locked(*, now: float | None = None) -> int:
    """移除过期条目，返回删除数量。调用方须已持有 _lock。"""
    if now is None:
        now = time.time()
    cutoff = now - MAX_AGE_SECONDS
    removed = 0
    while _buffer and _buffer[0].timestamp < cutoff:
        _buffer.popleft()
        removed += 1
    return removed


def setup_logging(level: int = logging.INFO) -> None:
    """安装内存 Handler（可重复调用，仅首次生效）。"""
    global _installed
    if _installed:
        return
    _installed = True

    root = logging.getLogger()
    root.setLevel(level)

    handler = MemoryLogHandler()
    handler.setLevel(level)
    # Formatter 仅用于兼容；实际缓冲用 LogEntry
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    logging.captureWarnings(True)

    for noisy in ("urllib3", "httpx", "httpcore", "uiautomation", "PIL", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("app").info(
        "日志已启动（Python %s，保留最近 %d 小时 / %d 条）",
        sys.version.split()[0],
        MAX_AGE_SECONDS // 3600,
        MAX_LINES,
    )


def split_content_message(message: str) -> tuple[str, str | None]:
    """拆分内容日志为 (标题, 正文)；非内容日志正文为 None。"""
    if CONTENT_SEP in (message or ""):
        header, body = message.split(CONTENT_SEP, 1)
        return header, body
    return message or "", None


def log_captured_content(
    kind: str,
    text: str,
    *,
    method: str | None = None,
    logger_name: str = "content",
) -> None:
    """记录划词 / OCR 内容：标题一行，正文完整另起一行（显示时加框）。"""
    parts = [kind]
    if method:
        parts.append(f"方式={method}")
    body = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts.append(f"长度={len(body.strip())}")
    header = " | ".join(parts)
    logging.getLogger(logger_name).info("%s%s%s", header, CONTENT_SEP, body)


def get_log_entries() -> list[LogEntry]:
    with _lock:
        _purge_locked()
        return list(_buffer)


def get_log_text() -> str:
    with _lock:
        _purge_locked()
        return "\n".join(entry.plain_line() for entry in _buffer)


def clear_logs(*, silent: bool = False) -> None:
    with _lock:
        _buffer.clear()
    if not silent:
        logging.getLogger("app").info("日志已清空")


def purge_expired_logs() -> int:
    """定时任务调用：清除过期日志。"""
    with _lock:
        removed = _purge_locked()
    if removed:
        logging.getLogger("app").info("已自动清除 %d 条过期日志", removed)
    return removed


def log_lines_count() -> int:
    with _lock:
        _purge_locked()
        return len(_buffer)


# 日志级别对应显示颜色（深色背景）
LEVEL_COLORS = {
    logging.DEBUG: "#8a8a8a",
    logging.INFO: "#7eb8da",
    logging.WARNING: "#e6a817",
    logging.ERROR: "#ff6b6b",
    logging.CRITICAL: "#ff3b3b",
}

TIMESTAMP_COLOR = "#6a9955"
NAME_COLOR = "#9cdcfe"
MESSAGE_COLOR = "#d4d4d4"
CONTENT_COLOR = "#e8d4b0"
CONTENT_BOX_BG = "#252526"
CONTENT_BOX_BORDER = "#088fff"


def _single_line(text: str) -> str:
    return " ".join((text or "").replace("\r", "\n").split())


def entry_to_html(entry: LogEntry) -> str:
    """单条日志转 HTML；识别内容另起一行并用边框框住。"""
    from html import escape

    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.timestamp))
    level_color = LEVEL_COLORS.get(entry.level, MESSAGE_COLOR)
    header, body = split_content_message(entry.message)

    head = (
        f'<div style="margin:0; padding:2px 0; line-height:1.35; white-space:nowrap">'
        f'<span style="color:{TIMESTAMP_COLOR}">{escape(ts)}</span> '
        f'<span style="color:{level_color}; font-weight:600">[{escape(entry.level_name)}]</span> '
        f'<span style="color:{NAME_COLOR}">{escape(entry.name)}</span>: '
        f'<span style="color:{MESSAGE_COLOR}">{escape(_single_line(header))}</span>'
        f"</div>"
    )

    if body is None:
        return f'<div style="margin:0 0 4px 0">{head}</div>'

    # 保留换行，不截断；用边框框住识别原文
    body_html = escape(body).replace("\n", "<br>")
    if not body.strip():
        body_html = escape("（空）")

    boxed = (
        f'<div style="'
        f"margin:2px 0 8px 12px; padding:6px 8px; "
        f"border:1px solid {CONTENT_BOX_BORDER}; border-radius:4px; "
        f"background:{CONTENT_BOX_BG}; "
        f"color:{CONTENT_COLOR}; white-space:pre-wrap; word-wrap:break-word; "
        f'line-height:1.4">'
        f"{body_html}"
        f"</div>"
    )
    return f'<div style="margin:0 0 6px 0">{head}{boxed}</div>'


def get_log_html() -> str:
    entries = get_log_entries()
    if not entries:
        return (
            f'<div style="color:#888888; font-family:Consolas,monospace; '
            f'font-size:{LOG_FONT_PX}px">（暂无日志）</div>'
        )
    body = "".join(entry_to_html(e) for e in entries)
    return (
        '<div style="font-family:Consolas,\"Microsoft YaHei UI\",monospace;'
        f' font-size:{LOG_FONT_PX}px; line-height:1.35">'
        f"{body}</div>"
    )
