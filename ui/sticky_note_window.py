"""桌面便签窗口：置顶 / 新增 / 换色 / 隐藏 / 关闭、拖拽与缩放、防抖本地保存。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sticky_notes_store import delete_note, new_note_id, upsert_note
from ui.base_window import FramelessWindow
from ui.constants import (
    BORDER_RADIUS,
    DEFAULT_NOTE_HEIGHT,
    DEFAULT_NOTE_WIDTH,
    HEADER_BTN_SIZE,
    ICON_SIZE,
    MIN_NOTE_HEIGHT,
    MIN_NOTE_WIDTH,
    NOTE_HEADER_HEIGHT,
    NOTE_WINDOW_ALPHA,
)
from ui.icons import IconButton
from ui.note_colors import contrast_text_color, is_dark_color, random_note_colors
from ui.note_confirm_dialog import NoteConfirmDialog
from ui.styles import note_scrollbar_qss, note_text_edit_qss
from ui.text_utils import install_placeholder_ime_fix
from ui.window_pin import apply_window_pin, toggle_window_pin

NOTE_PERSIST_DEBOUNCE_MS = 450


class _ColorSwatchButton(QPushButton):
    """标题栏颜色按钮：显示当前内容区色块。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._swatch = QColor("#F0B6F0")
        self.setFixedSize(HEADER_BTN_SIZE, HEADER_BTN_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def set_swatch_color(self, color: QColor):
        self._swatch = QColor(color)
        self._swatch.setAlpha(255)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = ICON_SIZE
        x = (self.width() - size) / 2
        y = (self.height() - size) / 2
        painter.setPen(QPen(QColor(0, 0, 0, 50), 1))
        painter.setBrush(self._swatch)
        painter.drawEllipse(QRectF(x, y, size, size))


class StickyNoteWindow(FramelessWindow):
    create_requested = Signal()

    def __init__(
        self,
        *,
        placement_physical: tuple[int, int] | None = None,
        placement_mode: str = "cursor",
        record: dict | None = None,
    ):
        super().__init__(show_header=False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle("便签")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(MIN_NOTE_WIDTH, MIN_NOTE_HEIGHT)

        self._note_id: str | None = None
        self._pinned = False
        self._content_color = QColor("#F0B6F0")
        self._header_color = QColor("#EFC1EF")
        self._drag_pos = None
        self._placement_physical = placement_physical
        self._placement_mode = placement_mode
        self._placement_applied = False
        self._loading = False
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.setInterval(NOTE_PERSIST_DEBOUNCE_MS)
        self._persist_timer.timeout.connect(self._persist_now)

        self.body.setContentsMargins(0, 0, 0, 0)
        self._build_ui()

        if record is not None:
            self._apply_record(record)
        else:
            self._apply_colors(self._content_color, self._header_color)
            self.resize(DEFAULT_NOTE_WIDTH, DEFAULT_NOTE_HEIGHT)
            self._randomize_color()
            if self._placement_physical is not None:
                self._apply_placement()

        self.enable_corner_resize(self._on_resize)
        self._border_overlay.hide()

    def _build_ui(self):
        root = QWidget()
        root.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._note_header = QWidget()
        self._note_header.setFixedHeight(NOTE_HEADER_HEIGHT)
        self._note_header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        header_layout = QHBoxLayout(self._note_header)
        header_layout.setContentsMargins(6, 0, 6, 0)
        header_layout.setSpacing(2)

        self.pin_btn = IconButton(
            "pin.svg", variant="on_light", button_size=HEADER_BTN_SIZE
        )
        self.add_btn = IconButton(
            "plus.svg", variant="on_light", button_size=HEADER_BTN_SIZE
        )
        self.color_btn = _ColorSwatchButton()
        self.hide_btn = IconButton(
            "minus.svg", variant="on_light", button_size=HEADER_BTN_SIZE
        )
        self.close_btn = IconButton(
            "close.svg", variant="on_light", button_size=HEADER_BTN_SIZE
        )

        header_layout.addWidget(self.pin_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.color_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch(1)
        header_layout.addWidget(self.hide_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._note_header.setCursor(Qt.CursorShape.SizeAllCursor)
        self._note_header.installEventFilter(self)

        self.textarea = QPlainTextEdit()
        self.textarea.setPlaceholderText("记点什么…")
        self.textarea.setFrameShape(QFrame.Shape.NoFrame)
        self.textarea.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.textarea.viewport().setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self.textarea.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        install_placeholder_ime_fix(self.textarea)

        layout.addWidget(self._note_header)
        layout.addWidget(self.textarea, 1)
        self.body.addWidget(root)

        self.pin_btn.clicked.connect(self._toggle_pin)
        self.add_btn.clicked.connect(self.create_requested.emit)
        self.color_btn.clicked.connect(self._randomize_color)
        self.hide_btn.clicked.connect(self._hide_note)
        self.close_btn.clicked.connect(self._request_close)
        self.textarea.textChanged.connect(self._schedule_persist)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)
        painter.fillPath(path, self._with_alpha(self._content_color))

        header_path = QPainterPath()
        header_rect = QRectF(0.5, 0.5, self.width() - 1, NOTE_HEADER_HEIGHT)
        header_path.addRect(header_rect)
        clipped = path.intersected(header_path)
        painter.fillPath(clipped, self._with_alpha(self._header_color))

        border = (
            QColor(255, 255, 255, 40)
            if is_dark_color(self._content_color)
            else QColor(0, 0, 0, 45)
        )
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    @staticmethod
    def _with_alpha(color: QColor, alpha: int = NOTE_WINDOW_ALPHA) -> QColor:
        c = QColor(color)
        c.setAlpha(max(0, min(255, int(alpha))))
        return c

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent

        if obj is self._note_header:
            et = event.type()
            if et == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                if self._note_header.childAt(event.position().toPoint()) is None:
                    self._drag_pos = (
                        event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    )
                    self.grabMouse()
                    return True
            elif et == QEvent.Type.MouseMove:
                if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            elif et == QEvent.Type.MouseButtonRelease:
                if self._drag_pos is not None:
                    self._drag_pos = None
                    if self.mouseGrabber() is self:
                        self.releaseMouse()
                    self._schedule_persist()
                    return True
        return super().eventFilter(obj, event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._drag_pos = None
            if self.mouseGrabber() is self:
                self.releaseMouse()
            self._schedule_persist()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if not self._loading and self.isVisible():
            self._schedule_persist()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._loading and self.isVisible():
            self._schedule_persist()

    def _apply_colors(self, content: QColor, header: QColor):
        self._content_color = QColor(content)
        self._header_color = QColor(header)
        self.color_btn.set_swatch_color(self._content_color)

        dark = is_dark_color(self._content_color)
        fg = contrast_text_color(self._content_color)
        placeholder = (
            QColor(255, 255, 255, 140) if dark else QColor(0, 0, 0, 100)
        )
        self.textarea.setStyleSheet(
            note_text_edit_qss(text_color=fg.name())
            + note_scrollbar_qss(dark_bg=dark)
        )
        pal = self.textarea.palette()
        pal.setColor(QPalette.ColorRole.Text, fg)
        pal.setColor(QPalette.ColorRole.PlaceholderText, placeholder)
        self.textarea.setPalette(pal)

        icon_variant = "light" if is_dark_color(self._header_color) else "on_light"
        for btn in (self.pin_btn, self.add_btn, self.hide_btn, self.close_btn):
            btn.set_variant(icon_variant)

        self.update()
        if not self._loading:
            self._schedule_persist()

    def _randomize_color(self):
        content, header = random_note_colors(avoid_content=self._content_color)
        self._apply_colors(content, header)

    def _toggle_pin(self):
        self._pinned = toggle_window_pin(self, self._pinned)
        self.pin_btn.set_active(self._pinned)
        self._schedule_persist()

    def set_pinned(self, pinned: bool):
        self._pinned = apply_window_pin(self, pinned)
        self.pin_btn.set_active(self._pinned)

    def is_pinned(self) -> bool:
        return self._pinned

    def note_id(self) -> str | None:
        return self._note_id

    def _apply_placement(self):
        if self._placement_applied or self._placement_physical is None:
            return
        from ui.screen_coords import place_window_near_physical

        px, py = self._placement_physical
        place_window_near_physical(self, px, py, mode=self._placement_mode)
        self._placement_applied = True

    def showEvent(self, event):
        if not self._placement_applied and self._placement_physical is not None:
            self._apply_placement()
        super().showEvent(event)

    def _on_resize(self, delta_x: int, delta_y: int):
        self.resize(
            max(MIN_NOTE_WIDTH, self.width() + delta_x),
            max(MIN_NOTE_HEIGHT, self.height() + delta_y),
        )
        self._schedule_persist()

    def _hide_note(self):
        self.flush_persist()
        self.hide()

    def _request_close(self):
        has_content = bool(self.textarea.toPlainText().strip())
        if has_content:
            dialog = NoteConfirmDialog(
                message="确定删除此便签？删除后不可恢复。",
                content_color=self._content_color,
                header_color=self._header_color,
                confirm_text="删除",
                cancel_text="取消",
                parent=self,
            )
            if dialog.exec() != NoteConfirmDialog.DialogCode.Accepted:
                return
        self._persist_timer.stop()
        if self._note_id:
            delete_note(self._note_id)
            self._note_id = None
        self.close()

    def _apply_record(self, record: dict):
        self._loading = True
        try:
            self._note_id = str(record.get("id") or "") or None
            content = QColor(str(record.get("content_color") or "#F0B6F0"))
            header = QColor(str(record.get("header_color") or "#EFC1EF"))
            if not content.isValid():
                content = QColor("#F0B6F0")
            if not header.isValid():
                header = QColor("#EFC1EF")
            self._apply_colors(content, header)

            w = max(MIN_NOTE_WIDTH, int(record.get("width", DEFAULT_NOTE_WIDTH)))
            h = max(MIN_NOTE_HEIGHT, int(record.get("height", DEFAULT_NOTE_HEIGHT)))
            x = int(record.get("x", 100))
            y = int(record.get("y", 100))
            self.setGeometry(x, y, w, h)
            self._placement_applied = True

            self.textarea.blockSignals(True)
            self.textarea.setPlainText(str(record.get("text") or ""))
            self.textarea.blockSignals(False)

            self.set_pinned(bool(record.get("pinned", False)))
        finally:
            self._loading = False

    def to_record(self) -> dict:
        text = self.textarea.toPlainText()
        nid = self._note_id or new_note_id()
        return {
            "id": nid,
            "text": text,
            "x": int(self.x()),
            "y": int(self.y()),
            "width": int(self.width()),
            "height": int(self.height()),
            "content_color": self._content_color.name(),
            "header_color": self._header_color.name(),
            "pinned": bool(self._pinned),
        }

    def _schedule_persist(self):
        if self._loading:
            return
        self._persist_timer.start()

    def _persist_now(self):
        text = self.textarea.toPlainText()
        if not text.strip():
            if self._note_id:
                delete_note(self._note_id)
                self._note_id = None
            return
        record = self.to_record()
        self._note_id = record["id"]
        upsert_note(record)

    def flush_persist(self):
        if self._persist_timer.isActive():
            self._persist_timer.stop()
        self._persist_now()

    def _raise_floating_controls(self):
        if self._resize_handle is not None:
            self._resize_handle.raise_()
        self._border_overlay.hide()
