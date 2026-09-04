"""工具箱共享样式与小组件。"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QBuffer, QSize, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.constants import BORDER_RADIUS, FONT_SIZE, WIDGET_MARGIN_H, WIDGET_MARGIN_V
from ui.icons import IconButton, load_icon
from ui.styles import COMBO_POPUP_VIEW_QSS
from ui.text_utils import disable_label_selection, install_placeholder_ime_fix
from ui.widgets import MarkCheckBox

R = BORDER_RADIUS

EDIT_QSS = f"""
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: #292929;
    color: #f2f2f2;
    border: 1px solid #333333;
    border-radius: {R}px;
    padding: {WIDGET_MARGIN_V}px {WIDGET_MARGIN_H}px;
    font-size: {FONT_SIZE}px;
    selection-background-color: #088fff;
    selection-color: #ffffff;
}}
QPlainTextEdit, QTextEdit {{
    font-family: "Microsoft YaHei UI", Consolas, monospace;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: #088fff;
}}
QPlainTextEdit QWidget, QTextEdit QWidget {{
    background: #292929;
}}
"""

INPUT_QSS = EDIT_QSS

COMBO_QSS = f"""
QComboBox {{
    background: #292929;
    color: #f2f2f2;
    border: 1px solid #333333;
    border-radius: {R}px;
    padding: 4px {WIDGET_MARGIN_H}px;
    min-height: 28px;
    font-size: {FONT_SIZE}px;
}}
QComboBox:hover {{
    border-color: #454545;
}}
QComboBox:disabled {{
    color: #888888;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
""" + COMBO_POPUP_VIEW_QSS

CARD_QSS = f"""
QFrame#toolCard {{
    background: #1a1a1a;
    border: 1px solid #333333;
    border-radius: {R}px;
}}
"""

MENU_BTN_QSS = f"""
QPushButton#sideMenuBtn {{
    background: transparent;
    border: none;
    border-radius: {R}px;
    color: #c8c8c8;
    text-align: left;
    padding: 8px 10px;
    font-size: 13px;
}}
QPushButton#sideMenuBtn:hover {{
    background: #2a2a2a;
    color: #ffffff;
}}
QPushButton#sideMenuBtn[active="true"] {{
    background: #2f2f2f;
    color: #ffffff;
}}
"""

EDGE_SCROLLBAR_QSS = """
QScrollBar:vertical {
    width: 6px;
    background: transparent;
    margin: 2px 0;
}
QScrollBar::handle:vertical {
    background: #555555;
    border: 1px solid transparent;
    border-radius: 999px;
    min-height: 24px;
    margin: 0;
}
QScrollBar::handle:vertical:hover {
    background: #666666;
}
QScrollBar::handle:vertical:pressed {
    background: #088fff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0;
    background: none;
}
QScrollBar:horizontal {
    height: 6px;
    background: transparent;
    margin: 0 2px;
}
QScrollBar::handle:horizontal {
    background: #555555;
    border: 1px solid transparent;
    border-radius: 999px;
    min-width: 24px;
    margin: 0;
}
QScrollBar::handle:horizontal:hover {
    background: #666666;
}
QScrollBar::handle:horizontal:pressed {
    background: #088fff;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0;
    background: none;
}
"""


def style_edit(widget: QLineEdit | QPlainTextEdit | QTextEdit) -> None:
    widget.setStyleSheet(EDIT_QSS + EDGE_SCROLLBAR_QSS)
    install_placeholder_ime_fix(widget)


def field_label(text: str) -> QLabel:
    lab = QLabel(text)
    disable_label_selection(lab)
    lab.setStyleSheet("color: #a0a0a0; font-size: 12px; background: transparent;")
    return lab


def mark_check_option(text: str, checked: bool = False) -> tuple[QWidget, MarkCheckBox]:
    """设置页风格勾选行：无背景；点文字等同点勾选框。"""
    wrap = QWidget()
    wrap.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    wrap.setStyleSheet("background: transparent; border: none;")
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    box = MarkCheckBox(checked=checked)
    lab = QLabel(text)
    disable_label_selection(lab)
    lab.setCursor(Qt.CursorShape.PointingHandCursor)
    lab.setStyleSheet("color:#c8c8c8;font-size:13px;background:transparent;")

    def _on_lab_press(_event: QMouseEvent) -> None:
        box.click()

    lab.mousePressEvent = _on_lab_press  # type: ignore[method-assign]
    lay.addWidget(box, 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addWidget(lab, 0, Qt.AlignmentFlag.AlignVCenter)
    return wrap, box


def status_label() -> QLabel:
    lab = QLabel("")
    disable_label_selection(lab)
    lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    set_status(lab, "")
    return lab


def set_status(lab: QLabel, text: str, ok: bool | None = None) -> None:
    lab.setText(text or "")
    if ok is True:
        color = "#5cb3ff"
    elif ok is False:
        color = "#ff6b6b"
    else:
        color = "#888888"
    lab.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")


def pixmap_to_png_bytes(pix: QPixmap) -> bytes | None:
    if pix.isNull():
        return None
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    return bytes(ba)


class SideMenuButton(QPushButton):
    def __init__(self, icon_name: str, text: str, tool_id: str, parent=None):
        super().__init__(parent)
        self.tool_id = tool_id
        self._icon_name = icon_name
        self.setObjectName("sideMenuBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setText(f"  {text}")
        self.setIconSize(QSize(16, 16))
        self.setFixedHeight(36)
        self.setStyleSheet(MENU_BTN_QSS)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        color = "#ffffff" if active else "#c8c8c8"
        self.setIcon(load_icon(self._icon_name, 16, color))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ImageDropZone(QFrame):
    files_dropped = Signal(list)
    clicked = Signal()
    image_pasted = Signal(bytes, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(160)
        self._set_border(False)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint = QLabel("拖拽 / 粘贴图片到此处，或点击选择文件")
        self._hint.setStyleSheet("color:#888;font-size:13px;border:none;background:transparent;")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)
        self._sub = QLabel("支持 PNG / JPG / GIF / WebP")
        self._sub.setStyleSheet("color:#666;font-size:12px;border:none;background:transparent;")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("border:none;background:transparent;")
        self._preview.hide()
        lay.addWidget(self._hint)
        lay.addWidget(self._sub)
        lay.addWidget(self._preview)
        self._pix: QPixmap | None = None

    def _set_border(self, active: bool) -> None:
        color = "#088fff" if active else "#444"
        self.setStyleSheet(
            f"QFrame{{background:#1a1a1a;border:1px dashed {color};border-radius:{R}px;}}"
        )

    def set_preview(self, pix: QPixmap | None) -> None:
        self._pix = pix
        if pix is None or pix.isNull():
            self._preview.hide()
            self._hint.show()
            self._sub.show()
            return
        self._hint.hide()
        self._sub.hide()
        self._preview.show()
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        if not self._pix or self._pix.isNull():
            return
        scaled = self._pix.scaled(
            max(40, self.width() - 24),
            max(40, self.height() - 24),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()
            self._set_border(True)

    def dragLeaveEvent(self, event):
        self._set_border(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._set_border(False)
        md = event.mimeData()
        paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile()] if md.hasUrls() else []
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        if md.hasImage():
            img = md.imageData()
            if isinstance(img, QImage) and not img.isNull():
                data = pixmap_to_png_bytes(QPixmap.fromImage(img))
                if data:
                    self.image_pasted.emit(data, "image/png")
                    event.acceptProposedAction()

    def keyPressEvent(self, event):
        from PySide6.QtGui import QKeySequence

        if event.matches(QKeySequence.StandardKey.Paste) and self.try_clipboard_image():
            return
        super().keyPressEvent(event)

    def try_clipboard_image(self) -> bool:
        from PySide6.QtGui import QGuiApplication

        clip = QGuiApplication.clipboard()
        md = clip.mimeData() if clip else None
        if not md or not md.hasImage():
            return False
        img = md.imageData()
        if not isinstance(img, QImage) or img.isNull():
            return False
        data = pixmap_to_png_bytes(QPixmap.fromImage(img))
        if not data:
            return False
        self.image_pasted.emit(data, "image/png")
        return True


class PreviewBox(QFrame):
    download_clicked = Signal()

    def __init__(self, empty_text: str = "", *, fixed_size: int | None = None, parent=None):
        super().__init__(parent)
        self._fixed = fixed_size
        if fixed_size:
            self.setFixedSize(fixed_size, fixed_size)
        else:
            self.setMinimumHeight(160)
        self.setStyleSheet(
            f"QFrame{{background:#1a1a1a;border:1px solid #333333;border-radius:{R}px;}}"
        )
        self._empty = QLabel(empty_text)
        self._empty.setStyleSheet("color:#666;font-size:13px;border:none;background:transparent;")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setStyleSheet("border:none;background:transparent;")
        self._img.hide()
        self._dl = IconButton("download.svg", size=14, variant="overlay", button_size=28)
        self._dl.setToolTip("下载")
        self._dl.hide()
        self._dl.clicked.connect(self.download_clicked.emit)
        self._dl.setParent(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addStretch(1)
        lay.addWidget(self._empty, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._img, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        self._pix: QPixmap | None = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._dl.move(self.width() - self._dl.width() - 8, 8)
        self._relayout()

    def clear(self) -> None:
        self._pix = None
        self._img.hide()
        self._img.clear()
        self._empty.show()
        self._dl.hide()

    def set_pixmap(self, pix: QPixmap | None) -> None:
        if pix is None or pix.isNull():
            self.clear()
            return
        self._pix = pix
        self._empty.hide()
        self._img.show()
        self._dl.show()
        self._dl.raise_()
        self._relayout()

    def _relayout(self) -> None:
        if not self._pix or self._pix.isNull():
            return
        scaled = self._pix.scaled(
            max(40, self.width() - 24),
            max(40, self.height() - 24),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._img.setPixmap(scaled)
