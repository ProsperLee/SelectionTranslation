import sys

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

from ui.constants import BORDER_RADIUS, HEADER_HEIGHT, ICON_SIZE
from ui.win_effects import set_window_topmost
from ui.widgets import ResizeHandleWidget


class _WindowBorderOverlay(QWidget):
    """画在最上层的窗口描边，避免贴边内容盖住边框线。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)
        painter.setPen(QPen(QColor("#373737")))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class FramelessWindow(QWidget):
    def __init__(self, title: str = "", show_header_border: bool = False, show_header: bool = True):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        qt_app = QApplication.instance()
        if qt_app is not None and not qt_app.windowIcon().isNull():
            self.setWindowIcon(qt_app.windowIcon())
        self._drag_pos = None
        self._stays_on_top = False
        self._show_header_border = show_header_border
        self._resize_handle: ResizeHandleWidget | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = QWidget()
        self.header.setFixedHeight(HEADER_HEIGHT if show_header else 0)
        self.header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if not show_header:
            self.header.hide()
        self.header.setStyleSheet("background: transparent;")
        self.header_layout = QVBoxLayout(self.header)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(0)

        self._header_separator: QFrame | None = None
        if show_header_border:
            self._header_separator = QFrame()
            self._header_separator.setFixedHeight(1)
            self._header_separator.setStyleSheet("background: #2a2a2a; border: none;")

        outer.addWidget(self.header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        self.body_widget = QWidget()
        self.body_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.body_widget.setStyleSheet("background: transparent;")
        self.body_widget.setLayout(self.body)
        outer.addWidget(self.body_widget, 1)

        self._border_overlay = _WindowBorderOverlay(self)

        if title and show_header:
            from PySide6.QtWidgets import QHBoxLayout, QLabel
            from ui.constants import FONT_SIZE, WIDGET_MARGIN_H
            from ui.text_utils import disable_label_selection

            layout = QHBoxLayout()
            layout.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
            label = QLabel(title)
            disable_label_selection(label)
            label.setStyleSheet(f"color: #ffffff; font-size: {FONT_SIZE}px; background: transparent;")
            layout.addWidget(label)
            self.set_header_layout(layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)
        painter.fillPath(path, QColor("#212121"))

    def enable_corner_resize(self, on_resize):
        self._resize_handle = ResizeHandleWidget(self)
        self._resize_handle.resized.connect(on_resize)
        self._resize_handle.drag_finished.connect(self._raise_floating_controls)
        self._place_resize_handle()
        self._raise_floating_controls()

    def _place_resize_handle(self):
        if self._resize_handle is None:
            return
        handle = self._resize_handle
        handle.move(
            self.width() - ICON_SIZE,
            self.height() - ICON_SIZE,
        )

    def _place_border_overlay(self):
        self._border_overlay.setGeometry(self.rect())

    def _raise_floating_controls(self):
        """子类覆盖：先提升面板内图标，再调用 super 确保描边与缩放手柄在最上层。"""
        self._border_overlay.raise_()
        if self._resize_handle is not None:
            self._resize_handle.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_border_overlay()
        self._place_resize_handle()
        self._raise_floating_controls()

    def showEvent(self, event):
        super().showEvent(event)
        self._place_border_overlay()
        self._raise_floating_controls()

    def set_header_layout(self, layout):
        from PySide6.QtWidgets import QSizePolicy

        while self.header_layout.count():
            item = self.header_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        wrapper = QWidget()
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        wrapper.setLayout(layout)
        self.header_layout.addWidget(wrapper, 1)
        if self._header_separator is not None:
            self.header_layout.addWidget(self._header_separator)

    def set_stays_on_top(self, enabled: bool) -> None:
        if (
            sys.platform == "win32"
            and set_window_topmost(int(self.winId()), enabled)
        ):
            self._stays_on_top = enabled
            if enabled:
                self.raise_()
            return

        geo = self.geometry()
        min_size = self.minimumSize()
        self.setUpdatesEnabled(False)
        try:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
            self.setMinimumSize(min_size)
            self.setGeometry(geo)
            self.resize(geo.size())
        finally:
            self.setUpdatesEnabled(True)
        self._stays_on_top = enabled
        self.show()
        self.raise_()

    def _header_drag_area(self) -> bool:
        return False

    def mousePressEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._header_drag_area()
            and event.position().y() <= HEADER_HEIGHT
        ):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
