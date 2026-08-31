from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QLabel, QLineEdit, QPlainTextEdit, QTextEdit


def disable_label_selection(label: QLabel) -> None:
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)


def enable_textarea_selection(editor: QPlainTextEdit) -> None:
    editor.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextEditorInteraction
    )


def enable_readonly_textarea_selection(editor: QPlainTextEdit | QTextEdit) -> None:
    editor.setReadOnly(True)
    editor.setCursorWidth(0)
    editor.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )


def install_placeholder_ime_fix(widget: QPlainTextEdit | QLineEdit | QTextEdit) -> None:
    """
    修复 Windows IME 预编辑时 placeholder 与输入文字重叠。

    Qt 在预上字阶段文档仍为空，会继续绘制 placeholder，叠在预编辑文字下方。
    """
    _PlaceholderImeFix(widget)


class _PlaceholderImeFix(QObject):
    def __init__(self, widget: QPlainTextEdit | QLineEdit | QTextEdit):
        super().__init__(widget)
        self._widget = widget
        self._placeholder = widget.placeholderText()
        self._composing = False
        widget.installEventFilter(self)
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda *_: self._sync())
        else:
            widget.textChanged.connect(self._sync)
        self._sync()

    def _has_text(self) -> bool:
        w = self._widget
        if isinstance(w, QLineEdit):
            return bool(w.text())
        return bool(w.toPlainText())

    def _sync(self) -> None:
        w = self._widget
        if not self._placeholder:
            self._placeholder = w.placeholderText()
        if self._has_text() or self._composing:
            if w.placeholderText():
                w.setPlaceholderText("")
        elif not w.placeholderText():
            w.setPlaceholderText(self._placeholder)

    def eventFilter(self, obj, event):
        if obj is not self._widget:
            return False
        et = event.type()
        if et == QEvent.Type.InputMethod:
            preedit = ""
            try:
                preedit = event.preeditString() or ""
            except Exception:
                pass
            self._composing = bool(preedit)
            QTimer.singleShot(0, self._sync)
        elif et == QEvent.Type.FocusOut:
            self._composing = False
            QTimer.singleShot(0, self._sync)
        return False


class NoSelectLineEdit(QLineEdit):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.deselect()

    def mousePressEvent(self, event):
        if self.isReadOnly():
            event.accept()
            return
        self.setCursorPosition(self.cursorPositionAt(event.position().toPoint()))
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def selectAll(self):
        pass

    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.StandardKey.SelectAll):
            event.accept()
            return
        super().keyPressEvent(event)
