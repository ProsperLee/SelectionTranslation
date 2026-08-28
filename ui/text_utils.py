from PySide6.QtCore import Qt
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
