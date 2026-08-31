"""全屏吸色：跨屏十字线、跟随鼠标的放大镜 HUD；Shift 切换 RGBA/HEX，左键或 C 复制并退出。"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QPoint, QRect, QSize, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from ui.constants import (
    COLOR_PICKER_MAG_CELL,
    COLOR_PICKER_MAG_COLS,
    COLOR_PICKER_MAG_ROWS,
    COLOR_PICKER_POPOVER_FONT_SIZE,
)

ROW_GAP = 4
POPOVER_BOTTOM_PAD = 8
SWATCH_SIZE = COLOR_PICKER_POPOVER_FONT_SIZE + 4
CROSSHAIR = QColor("#088fff")
CROSSHAIR_OVERLAY = QColor(8, 143, 255, 120)
CENTER_CELL_BORDER = QColor(0, 0, 0)
HUD_BG = QColor(0, 0, 0, int(255 * 0.8))
HUD_BORDER = QColor("#494949")
HUD_TEXT = QColor("#f2f2f2")
HUD_MUTED = QColor("#a8a8a8")
HINT_COPY = "左键或 C 复制颜色值"
HINT_SHIFT = "按 Shift 切换 RGBA/HEX"


class ColorPicker(QWidget):
    _active: "ColorPicker | None" = None
    _suppress_bubble_until: float = 0.0

    @classmethod
    def is_active(cls) -> bool:
        picker = cls._active
        if picker is None:
            return False
        if not picker.isVisible():
            cls._active = None
            return False
        return True

    @classmethod
    def suppresses_bubble(cls) -> bool:
        if cls.is_active():
            return True
        return time.time() < cls._suppress_bubble_until

    @classmethod
    def pick(cls, on_finished=None) -> bool:
        """开始吸色。on_finished(str | None) 为复制到剪贴板的色值；取消时为 None。"""
        if cls.is_active():
            return False
        screens = QGuiApplication.screens()
        if not screens:
            if on_finished:
                on_finished(None)
            return False
        picker = cls(on_finished)
        picker.show()
        return True

    def __init__(self, on_finished=None, parent=None):
        super().__init__(parent)
        self._on_finished = on_finished
        self._closed = False
        self._use_hex = True
        self._cursor = QPoint()
        self._color = QColor(0, 0, 0)
        self._screenshot = QPixmap()
        self._origin = QPoint()
        self._font = QFont("Microsoft YaHei UI", COLOR_PICKER_POPOVER_FONT_SIZE)
        self._right_pressed = False
        self._left_pressed = False

        self._track_timer = QTimer(self)
        self._track_timer.setInterval(16)
        self._track_timer.timeout.connect(self._track_cursor)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._screenshot, self._origin = self._grab_virtual_desktop()
        self.setGeometry(
            self._origin.x(),
            self._origin.y(),
            self._screenshot.width(),
            self._screenshot.height(),
        )
        ColorPicker._active = self

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
        self._track_cursor()
        self._track_timer.start()
        self.grabMouse()

    def hideEvent(self, event):
        self._track_timer.stop()
        if self.mouseGrabber() is self:
            self.releaseMouse()
        super().hideEvent(event)

    def _local_from_global(self) -> QPoint:
        return self.mapFromGlobal(QCursor.pos())

    def _track_cursor(self):
        if self._closed:
            return
        local = self._local_from_global()
        if local != self._cursor:
            self._update_at(local)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._cancel()
            event.accept()
            return
        if key == Qt.Key.Key_C:
            self._copy_and_finish()
            event.accept()
            return
        if key == Qt.Key.Key_Shift:
            if not event.isAutoRepeat():
                self._use_hex = not self._use_hex
                self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._right_pressed = True
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._left_pressed = True
            self._update_at(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton and self._right_pressed:
            self._right_pressed = False
            event.accept()
            # 等右键抬起后再关闭，避免 release 穿透到下层窗口
            QTimer.singleShot(0, self._cancel)
            return
        if event.button() == Qt.MouseButton.LeftButton and self._left_pressed:
            self._left_pressed = False
            self._update_at(event.position().toPoint())
            event.accept()
            QTimer.singleShot(0, self._copy_and_finish)
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self._update_at(event.position().toPoint())
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Windows 分层窗口：透明区域不收鼠标，需极低 alpha 全屏填充
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        if self._cursor.isNull():
            return
        self._paint_crosshair(painter)
        self._paint_hud(painter)

    def _update_at(self, local: QPoint):
        self._cursor = local
        self._color = self._sample_color(local.x(), local.y())
        self.update()

    def _sample_color(self, x: int, y: int) -> QColor:
        if self._screenshot.isNull():
            return QColor(0, 0, 0)
        img = self._screenshot.toImage()
        w, h = img.width(), img.height()
        if x < 0 or y < 0 or x >= w or y >= h:
            return QColor(0, 0, 0)
        return img.pixelColor(x, y)

    @staticmethod
    def _alpha_value(c: QColor) -> str:
        alpha = c.alpha() / 255.0
        if abs(alpha - 1.0) < 0.001:
            return "1"
        text = f"{alpha:.2f}".rstrip("0").rstrip(".")
        return text or "0"

    def _color_text(self) -> str:
        c = self._color
        if self._use_hex:
            return f"#{c.red():02X}{c.green():02X}{c.blue():02X}"
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {self._alpha_value(c)})"

    def _global_pos(self) -> tuple[int, int]:
        global_pt = self.mapToGlobal(self._cursor)
        return global_pt.x(), global_pt.y()

    def _font_metrics(self) -> QFontMetrics:
        return QFontMetrics(self._font)

    def _mag_size(self) -> tuple[int, int, int, int]:
        cols = COLOR_PICKER_MAG_COLS
        rows = COLOR_PICKER_MAG_ROWS
        cell = COLOR_PICKER_MAG_CELL
        return cols * cell, rows * cell, cols // 2, rows // 2

    def _hud_size(self) -> QSize:
        mag_w, mag_h, _, _ = self._mag_size()
        fm = self._font_metrics()
        line_h = fm.height()
        coord_text = f"({self._global_pos()[0]}, {self._global_pos()[1]})"
        color_row_w = SWATCH_SIZE + ROW_GAP + fm.horizontalAdvance(self._color_text())
        text_w = max(
            mag_w,
            fm.horizontalAdvance(coord_text),
            color_row_w,
            fm.horizontalAdvance(HINT_SHIFT),
            fm.horizontalAdvance(HINT_COPY),
        )
        inner_h = mag_h + ROW_GAP + line_h + ROW_GAP + max(SWATCH_SIZE, line_h)
        inner_h += ROW_GAP + line_h * 2 + POPOVER_BOTTOM_PAD
        return QSize(text_w, inner_h)

    def _hud_origin(self) -> QPoint:
        hud = self._hud_size()
        cx, cy = self._cursor.x(), self._cursor.y()
        offset = 20
        x = cx + offset
        y = cy + offset
        if x + hud.width() > self.width():
            x = cx - hud.width() - offset
        if y + hud.height() > self.height():
            y = cy - hud.height() - offset
        x = max(4, min(x, self.width() - hud.width() - 4))
        y = max(4, min(y, self.height() - hud.height() - 4))
        return QPoint(x, y)

    def _paint_crosshair(self, painter: QPainter):
        cx, cy = self._cursor.x(), self._cursor.y()
        painter.setPen(QPen(CROSSHAIR, 1))
        painter.drawLine(0, cy, self.width(), cy)
        painter.drawLine(cx, 0, cx, self.height())

    def _draw_centered_line(
        self,
        painter: QPainter,
        hud_rect: QRect,
        y: int,
        text: str,
        color: QColor,
    ) -> int:
        fm = self._font_metrics()
        line_h = fm.height()
        line_rect = QRect(hud_rect.x(), y, hud_rect.width(), line_h)
        painter.setPen(color)
        painter.drawText(
            line_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        return y + line_h

    def _paint_mag_crosshair(
        self,
        painter: QPainter,
        mag_x: int,
        mag_y: int,
        mag_w: int,
        mag_h: int,
        half_x: int,
        half_y: int,
    ) -> None:
        """放大镜内十字准线（中心采样格透明）+ 1px 边框。"""
        cell = COLOR_PICKER_MAG_CELL
        center_x = mag_x + half_x * cell
        center_y = mag_y + half_y * cell

        painter.fillRect(mag_x, center_y, half_x * cell, cell, CROSSHAIR_OVERLAY)
        painter.fillRect(center_x + cell, center_y, mag_w - (half_x + 1) * cell, cell, CROSSHAIR_OVERLAY)
        painter.fillRect(center_x, mag_y, cell, half_y * cell, CROSSHAIR_OVERLAY)
        painter.fillRect(center_x, center_y + cell, cell, mag_h - (half_y + 1) * cell, CROSSHAIR_OVERLAY)

        center_cell = QRect(center_x, center_y, cell, cell)
        painter.setPen(QPen(CENTER_CELL_BORDER, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(center_cell.adjusted(0, 0, -1, -1))

    def _paint_hud(self, painter: QPainter):
        hud_origin = self._hud_origin()
        hud_size = self._hud_size()
        hud_rect = QRect(hud_origin, hud_size)
        fm = self._font_metrics()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(HUD_BG))
        painter.drawRect(hud_rect)

        mag_w, mag_h, half_x, half_y = self._mag_size()
        cell = COLOR_PICKER_MAG_CELL
        cols = COLOR_PICKER_MAG_COLS
        rows = COLOR_PICKER_MAG_ROWS
        mag_x = hud_rect.x() + (hud_rect.width() - mag_w) // 2
        mag_y = hud_rect.y()

        img = self._screenshot.toImage()
        for row in range(rows):
            for col in range(cols):
                sx = self._cursor.x() + col - half_x
                sy = self._cursor.y() + row - half_y
                if 0 <= sx < img.width() and 0 <= sy < img.height():
                    color = img.pixelColor(sx, sy)
                else:
                    color = QColor(30, 30, 30)
                painter.fillRect(
                    QRect(
                        mag_x + col * cell,
                        mag_y + row * cell,
                        cell,
                        cell,
                    ),
                    color,
                )

        self._paint_mag_crosshair(painter, mag_x, mag_y, mag_w, mag_h, half_x, half_y)

        painter.setFont(self._font)
        y = mag_y + mag_h + ROW_GAP
        gx, gy = self._global_pos()
        y = self._draw_centered_line(painter, hud_rect, y, f"({gx}, {gy})", HUD_TEXT)

        color_text = self._color_text()
        color_row_h = max(SWATCH_SIZE, fm.height())
        row_y = y + ROW_GAP
        row_w = SWATCH_SIZE + ROW_GAP + fm.horizontalAdvance(color_text)
        row_x = hud_rect.x() + (hud_rect.width() - row_w) // 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._color))
        painter.drawRect(row_x, row_y + (color_row_h - SWATCH_SIZE) // 2, SWATCH_SIZE, SWATCH_SIZE)
        text_rect = QRect(
            row_x + SWATCH_SIZE + ROW_GAP,
            row_y,
            fm.horizontalAdvance(color_text),
            color_row_h,
        )
        painter.setPen(HUD_TEXT)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            color_text,
        )

        y = row_y + color_row_h + ROW_GAP
        y = self._draw_centered_line(painter, hud_rect, y, HINT_COPY, HUD_MUTED)
        self._draw_centered_line(painter, hud_rect, y, HINT_SHIFT, HUD_MUTED)

        painter.setPen(QPen(HUD_BORDER, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(hud_rect.adjusted(0, 0, -1, -1))

    def _copy_current(self) -> str:
        text = self._color_text()
        clip = QGuiApplication.clipboard()
        if clip is not None:
            clip.setText(text)
        return text

    def _copy_and_finish(self):
        text = self._copy_current()
        self._close_with(text)

    def _cancel(self):
        self._close_with(None)

    def _close_with(self, value: str | None):
        if self._closed:
            return
        self._closed = True
        self._track_timer.stop()
        self._right_pressed = False
        self._left_pressed = False
        if self.mouseGrabber() is self:
            self.releaseMouse()
        if ColorPicker._active is self:
            ColorPicker._active = None
        ColorPicker._suppress_bubble_until = time.time() + 2.0
        callback = self._on_finished
        self.hide()
        self.deleteLater()
        if callback:
            callback(value)
