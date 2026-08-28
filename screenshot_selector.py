"""全屏框选截图：Esc/右键取消；完成后回调 (pixmap, 鼠标物理坐标)。"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

OVERLAY_COLOR = QColor(0, 0, 0, 120)
SELECTION_BORDER = QColor("#088fff")
MIN_SELECTION = 5


class ScreenshotSelector(QWidget):
    _active: "ScreenshotSelector | None" = None
    _suppress_bubble_until: float = 0.0

    @classmethod
    def is_active(cls) -> bool:
        selector = cls._active
        if selector is None:
            return False
        if not selector.isVisible():
            cls._active = None
            return False
        return True

    @classmethod
    def suppresses_bubble(cls) -> bool:
        if cls.is_active():
            return True
        return time.time() < cls._suppress_bubble_until

    @classmethod
    def capture(cls, on_finished) -> bool:
        """开始截图选区。on_finished(QPixmap | None, anchor_xy | None)。"""
        if cls.is_active():
            return False
        screens = QGuiApplication.screens()
        if not screens:
            on_finished(None, None)
            return False
        selector = cls(on_finished)
        selector.show()
        return True

    def __init__(self, on_finished, parent=None):
        super().__init__(parent)
        self._on_finished = on_finished
        self._origin = QPoint()
        self._start = QPoint()
        self._selecting = False
        self._selection = QRect()
        self._screenshot = QPixmap()
        self._closed = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._screenshot, self._origin = self._grab_virtual_desktop()
        self.setGeometry(
            self._origin.x(),
            self._origin.y(),
            self._screenshot.width(),
            self._screenshot.height(),
        )
        ScreenshotSelector._active = self

    @staticmethod
    def _grab_virtual_desktop() -> tuple[QPixmap, QPoint]:
        screens = QGuiApplication.screens()
        min_x = min(screen.geometry().x() for screen in screens)
        min_y = min(screen.geometry().y() for screen in screens)
        max_x = max(screen.geometry().right() for screen in screens)
        max_y = max(screen.geometry().bottom() for screen in screens)
        width = max(1, max_x - min_x)
        height = max(1, max_y - min_y)

        canvas = QPixmap(width, height)
        canvas.fill(Qt.GlobalColor.black)
        painter = QPainter(canvas)
        for screen in screens:
            geo = screen.geometry()
            grab = screen.grabWindow(0)
            if not grab.isNull():
                painter.drawPixmap(geo.x() - min_x, geo.y() - min_y, grab)
        painter.end()
        return canvas, QPoint(min_x, min_y)

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._selecting = True
            self._selection = QRect()
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._selecting:
            current = event.position().toPoint()
            self._selection = QRect(self._start, current).normalized()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._selecting = False
            current = event.position().toPoint()
            rect = QRect(self._start, current).normalized()
            self._finish(rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._screenshot)
        painter.fillRect(self.rect(), OVERLAY_COLOR)

        if not self._selection.isNull():
            painter.drawPixmap(self._selection.topLeft(), self._screenshot, self._selection)
            painter.setPen(QPen(SELECTION_BORDER, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._selection)

    def _finish(self, rect: QRect):
        if (
            rect.width() < MIN_SELECTION
            or rect.height() < MIN_SELECTION
            or self._screenshot.isNull()
        ):
            self._cancel()
            return
        cropped = self._screenshot.copy(rect)
        self._close_with(cropped)

    def _cancel(self):
        self._close_with(None)

    def _close_with(self, pixmap: QPixmap | None):
        if self._closed:
            return
        self._closed = True
        if ScreenshotSelector._active is self:
            ScreenshotSelector._active = None
        ScreenshotSelector._suppress_bubble_until = time.time() + 1.5
        callback = self._on_finished
        anchor = None
        if pixmap is not None and not pixmap.isNull():
            from ui.screen_coords import cursor_physical_pos

            anchor = cursor_physical_pos()
        self.hide()
        self.deleteLater()
        callback(pixmap, anchor)
