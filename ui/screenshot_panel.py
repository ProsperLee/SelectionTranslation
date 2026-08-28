from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    Property,
    QPropertyAnimation,
    Qt,
    QPoint,
    QRect,
    QRectF,
    QSize,
)
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.constants import (
    BORDER_RADIUS,
    SNAPSHOT_WIDTH,
    WIDGET_MARGIN_H,
    WIDGET_MARGIN_V,
)
from ui.icons import IconButton
from ui.widgets import RoundedPanel
from ui.win_effects import apply_acrylic_blur

FROSTED_TINT_ALPHA = 145
FROSTED_NATIVE_OVERLAY_ALPHA = 36
FROSTED_FALLBACK_COLOR = QColor(20, 20, 24, 145)
FULLSCREEN_BOTTOM_BAR = 52
ZOOM_BUTTON_STEP = 1.1
ZOOM_WHEEL_BASE = 1.0010
ZOOM_ANIMATION_MS = 300


class ScreenshotImageView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = QPixmap()
        self._zoom = 1.0
        self._viewport_size = QSize()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_viewport_size(self, size: QSize):
        self._viewport_size = size

    def set_pixmap(self, pixmap: QPixmap):
        self._source = pixmap
        self._zoom = 1.0
        self.update()

    def set_zoom(self, zoom: float):
        if zoom <= 0:
            return
        self._zoom = zoom
        self.update()

    def zoom(self) -> float:
        return self._zoom

    def _fit_size(self) -> QSize:
        if not self._viewport_size.isEmpty():
            return self._viewport_size
        return self.size()

    def _base_display_pixmap(self) -> QPixmap:
        if self._source.isNull():
            return QPixmap()

        fit = self._fit_size()
        max_w, max_h = fit.width(), fit.height()
        if max_w <= 0 or max_h <= 0:
            return QPixmap()

        if self._source.width() <= max_w and self._source.height() <= max_h:
            return self._source

        return self._source.scaled(
            max_w,
            max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _display_pixmap(self) -> QPixmap:
        base = self._base_display_pixmap()
        if base.isNull():
            return QPixmap()
        if abs(self._zoom - 1.0) < 0.001:
            return base

        return base.scaled(
            max(1, int(base.width() * self._zoom)),
            max(1, int(base.height() * self._zoom)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _display_rect(self) -> QRect:
        pixmap = self._display_pixmap()
        if pixmap.isNull():
            return QRect()
        return QRect(
            (self.width() - pixmap.width()) // 2,
            (self.height() - pixmap.height()) // 2,
            pixmap.width(),
            pixmap.height(),
        )

    def paintEvent(self, event):
        pixmap = self._display_pixmap()
        if pixmap.isNull():
            return

        rect = self._display_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), BORDER_RADIUS, BORDER_RADIUS)
        painter.setClipPath(path)
        painter.drawPixmap(rect.topLeft(), pixmap)


class FullscreenImageCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = QPixmap()
        self._zoom = 1.0
        self._rotation = 0
        self._image_pos = QPoint(0, 0)
        self._dragging = False
        self._drag_start = QPoint()
        self._pos_start = QPoint()
        self._cached_base = QPixmap()
        self._cache_key = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def _invalidate_base_cache(self):
        self._cached_base = QPixmap()
        self._cache_key = None

    def _base_cache_key(self):
        return (
            self._rotation,
            self._source.cacheKey() if not self._source.isNull() else 0,
            self.width(),
            self.height(),
        )

    def set_pixmap(self, pixmap: QPixmap):
        self._source = pixmap
        self._zoom = 1.0
        self._rotation = 0
        self._image_pos = QPoint(0, 0)
        self._invalidate_base_cache()
        self._sync_image_position()
        self.update()

    def rotate_by(self, degrees: int):
        self._rotation = (self._rotation + degrees) % 360
        self._invalidate_base_cache()
        self._image_pos = self._centered_position()
        self.update()

    def oriented_source(self) -> QPixmap:
        if self._source.isNull():
            return QPixmap()
        if self._rotation % 360 == 0:
            return self._source
        transform = QTransform().rotate(self._rotation)
        return self._source.transformed(
            transform,
            Qt.TransformationMode.SmoothTransformation,
        )

    def set_zoom(self, zoom: float):
        if zoom <= 0:
            return
        was_pannable = self._can_pan()
        self._zoom = zoom
        if self._can_pan():
            if not was_pannable:
                self._image_pos = self._centered_position()
            else:
                self._image_pos = self._clamp_position(self._image_pos)
        else:
            self._image_pos = self._centered_position()
        self.update()

    def zoom(self) -> float:
        return self._zoom

    def _base_display_pixmap(self) -> QPixmap:
        cache_key = self._base_cache_key()
        if self._cache_key == cache_key and not self._cached_base.isNull():
            return self._cached_base

        source = self.oriented_source()
        if source.isNull() or self.width() <= 0 or self.height() <= 0:
            self._cached_base = QPixmap()
            self._cache_key = cache_key
            return self._cached_base

        max_w, max_h = self.width(), self.height()
        if source.width() <= max_w and source.height() <= max_h:
            self._cached_base = source
        else:
            self._cached_base = source.scaled(
                max_w,
                max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._cache_key = cache_key
        return self._cached_base

    def _display_size(self) -> QSize:
        base = self._base_display_pixmap()
        if base.isNull():
            return QSize()
        return QSize(
            max(1, int(base.width() * self._zoom)),
            max(1, int(base.height() * self._zoom)),
        )

    def _can_pan(self) -> bool:
        display = self._display_size()
        if display.isEmpty():
            return False
        return display.width() > self.width() or display.height() > self.height()

    def _centered_position(self) -> QPoint:
        display = self._display_size()
        return QPoint(
            (self.width() - display.width()) // 2,
            (self.height() - display.height()) // 2,
        )

    def _clamp_position(self, pos: QPoint) -> QPoint:
        display = self._display_size()
        if display.isEmpty():
            return pos

        vw, vh = self.width(), self.height()
        iw, ih = display.width(), display.height()
        x, y = pos.x(), pos.y()

        if self._can_pan():
            x = min(max(0, vw - iw), max(min(0, vw - iw), x))
            y = min(max(0, vh - ih), max(min(0, vh - ih), y))
        else:
            x = (vw - iw) // 2
            y = (vh - ih) // 2

        return QPoint(x, y)

    def _sync_image_position(self):
        if self._can_pan():
            self._image_pos = self._clamp_position(self._image_pos)
        else:
            self._image_pos = self._centered_position()

    def _update_cursor(self):
        if self._dragging:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._can_pan():
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._invalidate_base_cache()
        self._sync_image_position()
        self.update()

    def paintEvent(self, event):
        base = self._base_display_pixmap()
        if base.isNull():
            return

        size = self._display_size()
        pos = self._image_pos
        target = QRect(pos.x(), pos.y(), size.width(), size.height())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())
        path = QPainterPath()
        path.addRoundedRect(QRectF(target), BORDER_RADIUS, BORDER_RADIUS)
        painter.setClipPath(path)
        painter.drawPixmap(target, base, base.rect())

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._can_pan():
            self._dragging = True
            self._drag_start = event.position().toPoint()
            self._pos_start = self._image_pos
            self._update_cursor()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            delta = event.position().toPoint() - self._drag_start
            self._image_pos = self._clamp_position(self._pos_start + delta)
            self.update()
            event.accept()
            return
        self._update_cursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._update_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if not self._dragging:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)


class _ZoomAnimator(QObject):
    def __init__(self, canvas: FullscreenImageCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._zoom_value = 1.0
        self._animation = QPropertyAnimation(self, b"zoomValue")
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_zoom_value(self) -> float:
        return self._zoom_value

    def set_zoom_value(self, value: float):
        self._zoom_value = value
        self._canvas.set_zoom(value)

    zoomValue = Property(float, get_zoom_value, set_zoom_value)

    def _current_zoom(self) -> float:
        if self._animation.state() == QPropertyAnimation.State.Running:
            return float(self._animation.endValue())
        return self._canvas.zoom()

    def set_zoom_immediate(self, zoom: float):
        if zoom <= 0:
            return
        self._animation.stop()
        self._zoom_value = zoom
        self._canvas.set_zoom(zoom)

    def zoom_by(self, factor: float, *, fast: bool = False):
        current = self._current_zoom()
        target = current * factor
        if target <= 0 or abs(target - current) < 0.002:
            return

        if fast:
            self.set_zoom_immediate(target)
            return

        if self._animation.state() == QPropertyAnimation.State.Running:
            self._animation.setEndValue(target)
            return

        self._animation.stop()
        self._animation.setDuration(ZOOM_ANIMATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.setStartValue(current)
        self._animation.setEndValue(target)
        self._animation.start()


class _FrostedBackdrop(QWidget):
    def __init__(self, use_native_blur: bool = False, parent=None):
        super().__init__(parent)
        self._use_native_blur = use_native_blur
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_use_native_blur(self, enabled: bool):
        self._use_native_blur = enabled
        self.update()

    def paintEvent(self, event):
        if self._use_native_blur:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(16, 16, 20, FROSTED_NATIVE_OVERLAY_ALPHA))
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), FROSTED_FALLBACK_COLOR)


class ScreenshotFullscreenViewer(QWidget):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pixmap = pixmap
        self._blur_applied = False
        self._use_native_blur = False

        self._backdrop = _FrostedBackdrop(parent=self)

        self._canvas = FullscreenImageCanvas(self)
        self._canvas.set_pixmap(pixmap)

        self._zoom_animator = _ZoomAnimator(self._canvas, self)

        self.close_btn = IconButton("close.svg", variant="overlay", parent=self)
        self.close_btn.clicked.connect(self.close)

        self.rotate_ccw_btn = IconButton("rotate_ccw.svg", variant="overlay", parent=self)
        self.rotate_ccw_btn.clicked.connect(lambda: self._canvas.rotate_by(-90))

        self.rotate_cw_btn = IconButton("rotate_cw.svg", variant="overlay", parent=self)
        self.rotate_cw_btn.clicked.connect(lambda: self._canvas.rotate_by(90))

        self.zoom_out_btn = IconButton("zoom_out.svg", variant="overlay", parent=self)
        self.zoom_out_btn.clicked.connect(
            lambda: self._zoom_animator.zoom_by(1 / ZOOM_BUTTON_STEP)
        )

        self.zoom_in_btn = IconButton("zoom_in.svg", variant="overlay", parent=self)
        self.zoom_in_btn.clicked.connect(
            lambda: self._zoom_animator.zoom_by(ZOOM_BUTTON_STEP)
        )

        self.download_btn = IconButton("download.svg", variant="overlay", parent=self)
        self.download_btn.clicked.connect(self._download)

        screen = self.screen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        self.show()
        self._apply_frosted_effect()
        self._layout_controls()
        self.setFocus()

    def _apply_frosted_effect(self):
        hwnd = int(self.winId())
        self._use_native_blur = apply_acrylic_blur(
            hwnd,
            tint=(20, 20, 24, FROSTED_TINT_ALPHA),
        )
        self._backdrop.set_use_native_blur(self._use_native_blur)
        self._blur_applied = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._blur_applied:
            self._apply_frosted_effect()
        self._layout_controls()
        self.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_controls()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return
        factor = ZOOM_WHEEL_BASE ** delta
        self._zoom_animator.zoom_by(factor, fast=True)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def _viewport_size(self) -> QSize:
        return QSize(
            self.width(),
            max(1, self.height() - FULLSCREEN_BOTTOM_BAR),
        )

    def _layout_controls(self):
        self._backdrop.setGeometry(self.rect())
        self._backdrop.lower()

        viewport = self._viewport_size()
        self._canvas.setGeometry(0, 0, viewport.width(), viewport.height())
        self._canvas._sync_image_position()
        self._canvas.update()

        self.close_btn.move(
            self.width() - self.close_btn.width() - WIDGET_MARGIN_H,
            WIDGET_MARGIN_V,
        )

        buttons = [
            self.rotate_ccw_btn,
            self.rotate_cw_btn,
            self.zoom_out_btn,
            self.zoom_in_btn,
            self.download_btn,
        ]
        spacing = WIDGET_MARGIN_H
        total_width = sum(button.width() for button in buttons) + spacing * (len(buttons) - 1)
        x = (self.width() - total_width) // 2
        y = self.height() - WIDGET_MARGIN_V - buttons[0].height()
        for button in buttons:
            button.move(x, y)
            x += button.width() + spacing

        self._canvas.raise_()
        for button in buttons:
            button.raise_()
        self.close_btn.raise_()

    def _download(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存截图", "screenshot.png", "PNG (*.png);;JPEG (*.jpg)")
        if path:
            self._canvas.oriented_source().save(path)


class ScreenshotPanel(QWidget):
    def __init__(self, parent=None, screenshot: QPixmap | None = None):
        super().__init__(parent)
        # 截图区固定宽度，与左右面板布局一致
        policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        policy.setHorizontalStretch(0)
        self.setSizePolicy(policy)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("ScreenshotPanel { background: #1c1c1c; border: none; }")
        self._pixmap = screenshot if screenshot is not None and not screenshot.isNull() else self._create_placeholder()
        self._fullscreen_viewer: ScreenshotFullscreenViewer | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDGET_MARGIN_H, WIDGET_MARGIN_V, WIDGET_MARGIN_H, WIDGET_MARGIN_V)
        layout.setSpacing(0)

        self._image_frame = RoundedPanel("#1c1c1c", clip_children=True)
        frame_layout = QVBoxLayout(self._image_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self._image_view = ScreenshotImageView()
        frame_layout.addWidget(self._image_view, 1)
        layout.addWidget(self._image_frame, 1)

        self.fullscreen_btn = IconButton("fullscreen.svg", variant="overlay")
        self.fullscreen_btn.setParent(self)
        self.fullscreen_btn.clicked.connect(self._open_fullscreen)

        self.download_btn = IconButton("download.svg", variant="overlay")
        self.download_btn.setParent(self)
        self.download_btn.clicked.connect(self._download)
        self._refresh_image()

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(SNAPSHOT_WIDTH, hint.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1c1c1c"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.raise_floating_controls()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_floating_controls()

    def raise_floating_controls(self):
        self._image_frame.lower()
        self._image_view.lower()
        self.fullscreen_btn.raise_()
        self.download_btn.raise_()
        self._place_floating_controls()

    def _place_floating_controls(self):
        top = WIDGET_MARGIN_V
        right = self.width() - WIDGET_MARGIN_H

        self.download_btn.move(right - self.download_btn.width(), top)
        self.fullscreen_btn.move(
            right - self.download_btn.width() - 4 - self.fullscreen_btn.width(),
            top,
        )

    def _create_placeholder(self) -> QPixmap:
        pixmap = QPixmap(200, 300)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        painter.setPen(Qt.GlobalColor.darkGray)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Screenshot")
        painter.end()
        return pixmap

    def _refresh_image(self):
        self._image_view.set_pixmap(self._pixmap)
        self._place_floating_controls()

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._refresh_image()

    def _open_fullscreen(self):
        if self._pixmap.isNull():
            return
        if self._fullscreen_viewer is not None and self._fullscreen_viewer.isVisible():
            self._fullscreen_viewer.raise_()
            self._fullscreen_viewer.activateWindow()
            return
        self._fullscreen_viewer = ScreenshotFullscreenViewer(self._pixmap, self.window())
        self._fullscreen_viewer.destroyed.connect(self._clear_fullscreen_viewer)

    def _clear_fullscreen_viewer(self):
        self._fullscreen_viewer = None

    def _download(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存截图", "screenshot.png", "PNG (*.png);;JPEG (*.jpg)")
        if path:
            self._pixmap.save(path)
