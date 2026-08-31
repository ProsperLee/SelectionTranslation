"""
选区抓取：UIA 优先，其次经典编辑框 API，最后 WM_COPY（不注入 Ctrl+C）。

- get_selected_text：快捷键翻译用（可恢复前台窗口）
- peek_selection：划词按钮用
- 刻意不使用 keybd_event/keyboard 模拟 Ctrl+C，避免打断终端 / 触发软件快捷键
"""

from __future__ import annotations

import sys
import threading
import time
from ctypes import wintypes

try:
    import pyperclip

    HAS_PYPERCLIP = True
except ImportError:
    pyperclip = None  # type: ignore[assignment]
    HAS_PYPERCLIP = False

try:
    import uiautomation as uia

    HAS_UIA = True
except ImportError:
    uia = None  # type: ignore[assignment]
    HAS_UIA = False

from ui.constants import SELECTION_BUBBLE_SIZE

_clipboard_lock = threading.Lock()

if sys.platform == "win32":
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None  # type: ignore[assignment]
    kernel32 = None  # type: ignore[assignment]
    ctypes = None  # type: ignore[assignment]

VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
VK_LWIN = 0x5B
VK_RWIN = 0x5C
CF_UNICODETEXT = 13
WM_COPY = 0x0301
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
EM_GETSEL = 0x00B0
GMEM_MOVEABLE = 0x0002

_MODIFIER_VKS = (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)


def foreground_hwnd() -> int | None:
    if user32 is None:
        return None
    try:
        return int(user32.GetForegroundWindow())
    except Exception:
        return None


def force_foreground(hwnd: int | None) -> bool:
    """尽量把目标窗口拉回前台（AttachThreadInput 绕过焦点限制）。"""
    if user32 is None or kernel32 is None or not hwnd:
        return False
    try:
        hwnd = int(hwnd)
        current = int(user32.GetForegroundWindow() or 0)
        if current == hwnd:
            return True

        fg_tid = user32.GetWindowThreadProcessId(current, None) if current else 0
        target_tid = user32.GetWindowThreadProcessId(hwnd, None)
        cur_tid = kernel32.GetCurrentThreadId()

        attached_fg = False
        attached_target = False
        if fg_tid and fg_tid != cur_tid:
            attached_fg = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
        if target_tid and target_tid != cur_tid and target_tid != fg_tid:
            attached_target = bool(user32.AttachThreadInput(cur_tid, target_tid, True))

        try:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.03)
            return int(user32.GetForegroundWindow() or 0) == hwnd
        finally:
            if attached_target:
                user32.AttachThreadInput(cur_tid, target_tid, False)
            if attached_fg:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
    except Exception:
        return False


def get_selected_text(prefer_hwnd=None) -> tuple[str, str]:
    """
    获取用户选中的文本。
    prefer_hwnd: 弹窗已抢焦点时，先切回该窗口再抓取。
    返回 (文本, 获取方式)：uia / edit / wm_copy。
    """
    if prefer_hwnd and user32 is not None:
        try:
            current = int(user32.GetForegroundWindow() or 0)
            if prefer_hwnd != current:
                force_foreground(int(prefer_hwnd))
        except Exception:
            pass

    # 等快捷键修饰键松开，避免仍按住 Alt/Shift 时部分应用读不到选区
    _wait_modifiers_released(timeout=0.5)

    if HAS_UIA:
        try:
            text, _anchor = get_uia_selection()
            if text and text.strip():
                return text, "uia"
        except Exception:
            pass

    text = _get_text_via_edit_api(prefer_hwnd=prefer_hwnd)
    if text:
        return text, "edit"

    text = _get_text_via_wm_copy(prefer_hwnd=prefer_hwnd)
    return text, "wm_copy"


def peek_selection(
    cursor_x: int | None = None,
    cursor_y: int | None = None,
) -> tuple[str, tuple[int, int] | None]:
    """
    读取当前选区。优先 UIA，再编辑框 API / WM_COPY（不注入 Ctrl+C）。
    返回 (文本, 选区末尾屏幕坐标或 None)。
    """
    # 本进程 Qt 文本框（如便签）须在 GUI 线程用 Qt API，UIA 锚点常不准
    qt_text, qt_anchor = peek_qt_text_selection()
    if qt_text:
        return qt_text, qt_anchor

    text, anchor = get_uia_selection(cursor_x, cursor_y)
    if text.strip():
        return text, anchor
    text = _get_text_via_edit_api(prefer_hwnd=foreground_hwnd())
    if text:
        return text, None
    text = _get_text_via_wm_copy(prefer_hwnd=foreground_hwnd())
    return (text or "").strip(), None


def peek_qt_text_selection() -> tuple[str, tuple[int, int] | None]:
    """
    读取本进程内 QPlainTextEdit / QTextEdit 的选区与末尾锚点（物理坐标）。
    必须在 Qt GUI 线程调用；非 GUI 线程或无选区时返回 ("", None)。
    """
    try:
        from PySide6.QtCore import QThread
        from PySide6.QtGui import QTextCursor
        from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTextEdit

        from ui.constants import SELECTION_BUBBLE_SIZE
        from ui.screen_coords import qt_global_to_physical
    except Exception:
        return "", None

    app = QApplication.instance()
    if app is None or QThread.currentThread() is not app.thread():
        return "", None

    widget = app.focusWidget()
    if not isinstance(widget, (QPlainTextEdit, QTextEdit)):
        return "", None

    cursor = widget.textCursor()
    if not cursor.hasSelection():
        return "", None

    raw = cursor.selectedText() or ""
    # QTextDocument 用 U+2029 表示段落分隔
    text = raw.replace("\u2029", "\n").strip()
    if not text:
        return "", None

    end_cursor = QTextCursor(cursor)
    end_cursor.setPosition(cursor.selectionEnd())
    # cursorRect 相对 viewport
    rect = widget.cursorRect(end_cursor)
    viewport = widget.viewport()
    top_left = viewport.mapToGlobal(rect.topRight())
    # 按钮贴在选区末字右侧、行高居中
    qx = int(top_left.x()) + 2
    qy = int(top_left.y()) + max(0, (rect.height() - SELECTION_BUBBLE_SIZE) // 2)
    return text, qt_global_to_physical(qx, qy)


def get_uia_selection(
    cursor_x: int | None = None,
    cursor_y: int | None = None,
) -> tuple[str, tuple[int, int] | None]:
    """返回 (选中文本, 选区末尾锚点屏幕坐标或 None)。"""
    if not HAS_UIA:
        return "", None
    try:
        initializer = getattr(uia, "UIAutomationInitializerInThread", None)
        if initializer is None:
            return _get_uia_selection_impl(cursor_x, cursor_y)
        with initializer():
            return _get_uia_selection_impl(cursor_x, cursor_y)
    except Exception:
        return "", None


def _is_placeholder_uia_text(text: str) -> bool:
    lowered = text.lower()
    return (
        "not accessible at this time" in lowered
        or "screen reader optimized mode" in lowered
    )


def _starting_controls(
    cursor_x: int | None,
    cursor_y: int | None,
) -> list:
    starts = []
    if cursor_x is not None and cursor_y is not None:
        try:
            hit = uia.ControlFromPoint(int(cursor_x), int(cursor_y))
            if hit is not None:
                starts.append(hit)
        except Exception:
            pass
    try:
        focused = uia.GetFocusedControl()
        if focused is not None and focused not in starts:
            starts.append(focused)
    except Exception:
        pass
    return starts


def _try_text_pattern_on_control(control) -> tuple[str, tuple[int, int] | None]:
    try:
        text_pattern = control.GetTextPattern()
        if text_pattern is None:
            return "", None
        selection = text_pattern.GetSelection()
        if not selection:
            return "", None
        chunks: list[str] = []
        anchor: tuple[int, int] | None = None
        for item in selection:
            part = (item.GetText(-1) or "").replace("\ufffc", "")
            if part:
                chunks.append(part)
            try:
                rects = item.GetBoundingRectangles()
                point = _selection_anchor_from_rects(rects)
                if point is not None:
                    anchor = point
            except Exception:
                pass
        text = "".join(chunks).strip()
        if not text or _is_placeholder_uia_text(text):
            return "", None
        return text, anchor
    except Exception:
        return "", None


def _try_legacy_iaccessible_on_control(control) -> str:
    try:
        lip = control.GetLegacyIAccessiblePattern()
        if lip is None:
            return ""
        for child in lip.GetSelection() or []:
            text, _anchor = _try_text_pattern_on_control(child)
            if text:
                return text
        value = (lip.Value or "").strip()
        if value and not _is_placeholder_uia_text(value):
            return value
    except Exception:
        pass
    return ""


def _walk_up_try_selection(start, max_depth: int = 10) -> tuple[str, tuple[int, int] | None]:
    cur = start
    for _ in range(max_depth):
        if cur is None:
            break
        text, anchor = _try_text_pattern_on_control(cur)
        if text:
            return text, anchor
        text = _try_legacy_iaccessible_on_control(cur)
        if text:
            return text, None
        try:
            cur = cur.GetParentControl()
        except Exception:
            break
    return "", None


def _find_monaco_editor(hwnd: int | None):
    if not hwnd:
        return None
    try:
        root = uia.ControlFromHandle(int(hwnd))
    except Exception:
        return None
    if root is None:
        return None

    stack = [root]
    best = None
    while stack:
        control = stack.pop()
        try:
            cls = (control.ClassName or "").lower()
            aid = (control.AutomationId or "").lower()
            ctype = getattr(control, "ControlTypeName", "") or ""
            if "inputarea" in cls or aid in ("editor", "monaco-editor"):
                if "Edit" in ctype or ctype.endswith("Control"):
                    best = control
            child = control.GetFirstChildControl()
            while child is not None:
                stack.append(child)
                child = child.GetNextSiblingControl()
        except Exception:
            continue
    return best


def _get_uia_selection_impl(
    cursor_x: int | None,
    cursor_y: int | None,
) -> tuple[str, tuple[int, int] | None]:
    for start in _starting_controls(cursor_x, cursor_y):
        text, anchor = _walk_up_try_selection(start)
        if text:
            return text, anchor

    editor = _find_monaco_editor(foreground_hwnd())
    if editor is not None:
        text, anchor = _walk_up_try_selection(editor)
        if text:
            return text, anchor

    return "", None


def _selection_anchor_from_rects(rects) -> tuple[int, int] | None:
    """取选区最后一个包围盒的右侧，贴近末行垂直居中（多行时贴底行）。"""
    box = _normalize_last_rect(rects)
    if box is None:
        return None
    left, top, right, bottom = box
    if right <= 0 and bottom <= 0 and left <= 0 and top <= 0:
        return None
    x = right + 2
    height = max(1, bottom - top)
    bubble_size = SELECTION_BUBBLE_SIZE
    if height <= bubble_size * 1.5:
        # 单行 / 矮选区：垂直居中于该行
        y = top + (height - bubble_size) // 2
    else:
        # 多行整块包围盒：贴末行底部，避免落在选区正中
        y = bottom - bubble_size
    return x, y


def _normalize_last_rect(rects) -> tuple[int, int, int, int] | None:
    """统一解析 UIA 包围盒为 (left, top, right, bottom)。"""
    if not rects:
        return None
    try:
        items = list(rects)
    except Exception:
        return None
    if not items:
        return None

    # 常见：平铺 float [l, t, w, h, ...]
    if all(isinstance(v, (int, float)) for v in items):
        if len(items) < 4:
            return None
        # 取最后一组
        n = len(items) - (len(items) % 4)
        if n < 4:
            return None
        left, top, width, height = (float(items[n - 4 + i]) for i in range(4))
        return int(left), int(top), int(left + width), int(top + height)

    last = items[-1]
    try:
        if isinstance(last, (tuple, list)) and len(last) >= 4:
            left, top, a, b = (float(last[i]) for i in range(4))
            # 可能是 l,t,w,h 或 l,t,r,b
            if a >= left and b >= top and (a - left) > 2 and (b - top) > 2:
                # 更像 right/bottom
                return int(left), int(top), int(a), int(b)
            return int(left), int(top), int(left + a), int(top + b)

        left = int(getattr(last, "left", 0) or 0)
        top = int(getattr(last, "top", 0) or 0)
        right = int(getattr(last, "right", 0) or 0)
        bottom = int(getattr(last, "bottom", 0) or 0)
        if right <= left and hasattr(last, "width"):
            right = left + int(last.width())
        if bottom <= top and hasattr(last, "height"):
            bottom = top + int(last.height())
        return left, top, right, bottom
    except Exception:
        return None


def _key_down(vk: int) -> bool:
    if user32 is None:
        return False
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _wait_modifiers_released(timeout: float = 0.5) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if not any(_key_down(vk) for vk in _MODIFIER_VKS):
            time.sleep(0.02)
            if not any(_key_down(vk) for vk in _MODIFIER_VKS):
                return
        time.sleep(0.01)


def _focus_hwnd() -> int | None:
    if user32 is None or ctypes is None:
        return None
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class GUITHREADINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND),
                ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND),
                ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND),
                ("hwndCaret", wintypes.HWND),
                ("rcCaret", RECT),
            ]

        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        fg = user32.GetForegroundWindow()
        tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        if tid and user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
            hwnd = int(info.hwndFocus or 0) or int(info.hwndCaret or 0)
            if hwnd:
                return hwnd
        return int(fg) if fg else None
    except Exception:
        return None


def _window_class(hwnd: int) -> str:
    if user32 is None or ctypes is None or not hwnd:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(int(hwnd), buf, 256)
        return buf.value or ""
    except Exception:
        return ""


def _get_edit_selection(hwnd: int | None) -> str:
    """从 Edit / RichEdit 控件直接读选区（不经剪贴板、不发按键）。"""
    if user32 is None or ctypes is None or not hwnd:
        return ""
    try:
        hwnd = int(hwnd)
        start = wintypes.DWORD()
        end = wintypes.DWORD()
        user32.SendMessageW(hwnd, EM_GETSEL, ctypes.byref(start), ctypes.byref(end))
        if start.value >= end.value:
            return ""

        length = int(user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0) or 0)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, buf)
        text = buf.value or ""
        return text[start.value : end.value].strip()
    except Exception:
        return ""


def _candidate_hwnds(prefer_hwnd: int | None) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for hwnd in (_focus_hwnd(), prefer_hwnd, foreground_hwnd()):
        if not hwnd:
            continue
        hwnd = int(hwnd)
        if hwnd in seen:
            continue
        seen.add(hwnd)
        result.append(hwnd)
        # 再向上找一层父窗口（部分嵌套编辑框）
        try:
            parent = int(user32.GetParent(hwnd) or 0) if user32 else 0
        except Exception:
            parent = 0
        if parent and parent not in seen:
            seen.add(parent)
            result.append(parent)
    return result


def _get_text_via_edit_api(prefer_hwnd: int | None = None) -> str:
    for hwnd in _candidate_hwnds(prefer_hwnd):
        cls = _window_class(hwnd).lower()
        # 常见可编辑类；其它窗口 EM_GETSEL 通常无害地返回空
        if cls and not any(
            key in cls
            for key in (
                "edit",
                "richedit",
                "text",
                "scintilla",
                "notepad",
            )
        ):
            # 仍尝试一次：部分自定义控件也响应 EM_GETSEL
            pass
        text = _get_edit_selection(hwnd)
        if text:
            return text
    return ""


def _clipboard_sequence() -> int:
    if user32 is None:
        return 0
    try:
        return int(user32.GetClipboardSequenceNumber())
    except Exception:
        return 0


def _read_clipboard_text() -> str:
    text = _read_clipboard_win32()
    if text is not None:
        return text
    if HAS_PYPERCLIP:
        try:
            return pyperclip.paste() or ""
        except Exception:
            return ""
    return ""


def _read_clipboard_win32() -> str | None:
    if user32 is None or kernel32 is None or ctypes is None:
        return None
    for _ in range(8):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.01)
    else:
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr) or ""
        finally:
            kernel32.GlobalUnlock(handle)
    except Exception:
        return None
    finally:
        user32.CloseClipboard()


def _write_clipboard_text(text: str) -> bool:
    if user32 is None or kernel32 is None or ctypes is None:
        if HAS_PYPERCLIP:
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                return False
        return False

    data = (text or "").encode("utf-16-le") + b"\x00\x00"
    for _ in range(8):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.01)
    else:
        return False
    try:
        user32.EmptyClipboard()
        alloc = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not alloc:
            return False
        lock = kernel32.GlobalLock(alloc)
        if not lock:
            kernel32.GlobalFree(alloc)
            return False
        ctypes.memmove(lock, data, len(data))
        kernel32.GlobalUnlock(alloc)
        if not user32.SetClipboardData(CF_UNICODETEXT, alloc):
            kernel32.GlobalFree(alloc)
            return False
        return True
    except Exception:
        return False
    finally:
        user32.CloseClipboard()


def _send_wm_copy(hwnd: int | None) -> None:
    """向窗口发送 WM_COPY：复制选区到剪贴板，不会注入 Ctrl+C 按键。"""
    if user32 is None or not hwnd:
        return
    try:
        user32.SendMessageW(int(hwnd), WM_COPY, 0, 0)
    except Exception:
        pass


def _wait_clipboard_change(prev_seq: int, timeout: float = 0.5) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if _clipboard_sequence() != prev_seq:
            return True
        time.sleep(0.012)
    return False


def _restore_clipboard(text: str) -> bool:
    """尽量恢复剪贴板原文，多次重试。"""
    for _ in range(5):
        if _write_clipboard_text(text):
            # 确认写回成功（空串也要能写回，表示「清空」是预期时才允许）
            time.sleep(0.01)
            return True
        time.sleep(0.02)
    if HAS_PYPERCLIP:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            pass
    return False


def _get_text_via_wm_copy(prefer_hwnd: int | None = None) -> str:
    """
    通过 WM_COPY 取选区（不模拟键盘）。
    不主动清空剪贴板；仅在确有改动时再写回原内容。
    """
    if not _clipboard_lock.acquire(timeout=2.0):
        return ""
    try:
        old_content = _read_clipboard_text()
        old_seq = _clipboard_sequence()

        if prefer_hwnd:
            force_foreground(prefer_hwnd)

        selected = ""
        changed = False
        for hwnd in _candidate_hwnds(prefer_hwnd):
            seq_before = _clipboard_sequence()
            _send_wm_copy(hwnd)
            if not _wait_clipboard_change(seq_before, timeout=0.35):
                continue
            changed = True
            current = _read_clipboard_text()
            if current and current.strip():
                selected = current.strip()
                break

        # 只要剪贴板被改过（含复制出空内容），就恢复原文，避免留下空条目
        if changed or _clipboard_sequence() != old_seq:
            _restore_clipboard(old_content)

        return selected
    finally:
        _clipboard_lock.release()
