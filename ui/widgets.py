from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRegion,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from ui.constants import (
    BORDER_RADIUS,
    COMBO_POPUP_FONT_SIZE,
    COMBO_POPUP_H_PADDING,
    COMBO_POPUP_MAX_VISIBLE,
    COMBO_POPUP_ROW_HEIGHT,
    FONT_SIZE,
    ICON_SIZE,
    SPLIT_LINE_BLOCK_HEIGHT,
    WIDGET_MARGIN_H,
    WIDGET_MARGIN_V,
)
from ui.icons import ICON_ACCENT, load_pixmap
from ui.styles import COMBO_POPUP_LIST_QSS, COMBO_QSS, INPUT_QSS, SCROLLBAR_QSS, SERVICE_COMBO_QSS
from ui.text_utils import NoSelectLineEdit, disable_label_selection

COMBO_POPUP_ITEM_MARGIN_H = WIDGET_MARGIN_H
COMBO_POPUP_ITEM_RADIUS = BORDER_RADIUS
COMBO_POPUP_SELECT_BG = "#1a5fb4"
COMBO_POPUP_TEXT = "#d4d4d4"
COMBO_POPUP_TEXT_ACTIVE = "#ffffff"
COMBO_POPUP_TEXT_PAD_H = WIDGET_MARGIN_H + 4


def _combo_popup_font(base: QFont | None = None) -> QFont:
    font = QFont(base) if base is not None else QFont()
    font.setPixelSize(COMBO_POPUP_FONT_SIZE)
    return font


class _ComboPopupDelegate(QStyledItemDelegate):
    _POPUP_ALIGNMENT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def initStyleOption(self, option: QStyleOptionViewItem, index):
        super().initStyleOption(option, index)
        option.displayAlignment = self._POPUP_ALIGNMENT
        option.textElideMode = Qt.TextElideMode.ElideNone
        option.showDecorationSelected = False
        option.font = _combo_popup_font(option.font)

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        metrics = QFontMetrics(_combo_popup_font(option.font))
        width = metrics.horizontalAdvance(text) + COMBO_POPUP_TEXT_PAD_H * 2
        return QSize(width, COMBO_POPUP_ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        active = selected or hovered

        if active:
            bg_rect = option.rect.adjusted(
                COMBO_POPUP_ITEM_MARGIN_H,
                1,
                -COMBO_POPUP_ITEM_MARGIN_H,
                -1,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COMBO_POPUP_SELECT_BG))
            painter.drawRoundedRect(
                bg_rect,
                COMBO_POPUP_ITEM_RADIUS,
                COMBO_POPUP_ITEM_RADIUS,
            )

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        painter.setFont(_combo_popup_font(option.font))
        painter.setPen(QColor(COMBO_POPUP_TEXT_ACTIVE if active else COMBO_POPUP_TEXT))
        text_rect = option.rect.adjusted(COMBO_POPUP_TEXT_PAD_H, 0, -COMBO_POPUP_TEXT_PAD_H, 0)
        painter.drawText(text_rect, int(self._POPUP_ALIGNMENT), text)
        painter.restore()


class _AlignComboBox(QComboBox):
    def __init__(self, display_alignment: Qt.AlignmentFlag, stylesheet: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(stylesheet)
        self.setItemDelegate(_ComboPopupDelegate(self))
        self.setEditable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        line_edit = NoSelectLineEdit(self)
        line_edit.setReadOnly(True)
        line_edit.setFrame(False)
        line_edit.setAlignment(display_alignment)
        line_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        line_edit.setStyleSheet("background: transparent; border: none; color: #f2f2f2;")
        line_edit.installEventFilter(self)
        self.setLineEdit(line_edit)

    def _configure_popup_view(self):
        view = self.view()
        if view is None:
            return None
        self.setMaxVisibleItems(COMBO_POPUP_MAX_VISIBLE)
        popup_font = _combo_popup_font(self.font())
        view.setFont(popup_font)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setUniformItemSizes(True)
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        view.setStyleSheet(COMBO_POPUP_LIST_QSS + SCROLLBAR_QSS)
        metrics = QFontMetrics(popup_font)
        max_text_width = max(
            (metrics.horizontalAdvance(self.itemText(i)) for i in range(self.count())),
            default=0,
        )
        # 文字完整显示：测宽 + 左右内边距 + 列表 padding / 滚动条余量
        popup_width = max(
            self.width(),
            max_text_width + COMBO_POPUP_TEXT_PAD_H * 2 + COMBO_POPUP_H_PADDING,
        )
        view.setMinimumWidth(popup_width)
        view.setFixedWidth(popup_width)
        popup = view.window()
        if popup is not None:
            popup.setStyleSheet(
                f"background: #1e1e1e; border: none; border-radius: {BORDER_RADIUS}px;"
            )
        return view

    def _resize_popup(self, view):
        popup = view.window()
        if popup is None:
            return
        visible_rows = min(self.count(), self.maxVisibleItems())
        pad = WIDGET_MARGIN_V
        popup_height = visible_rows * COMBO_POPUP_ROW_HEIGHT + pad
        width = max(view.minimumWidth(), view.width())
        view.setFixedWidth(width)
        popup.resize(width, popup_height)

    def _position_popup_left(self, view):
        popup = view.window()
        if popup is None:
            return
        popup.move(self.mapToGlobal(QPoint(0, 0)).x(), popup.y())

    def _is_popup_visible(self) -> bool:
        view = self.view()
        if view is None:
            return False
        popup = view.window()
        return popup is not None and popup.isVisible()

    def _pointer_over_self(self) -> bool:
        return self.rect().contains(self.mapFromGlobal(QCursor.pos()))

    def eventFilter(self, watched, event):
        if watched is self.lineEdit() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._open_popup()
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_popup()
            event.accept()
            return
        super().mousePressEvent(event)

    def hidePopup(self):
        # 下拉已打开时再点本框：不关闭；点其他区域才关闭
        if self._pointer_over_self():
            return
        super().hidePopup()

    def _open_popup(self):
        if self._is_popup_visible():
            return
        self.setFocus()
        self.showPopup()

    def showPopup(self):
        view = self._configure_popup_view()
        super().showPopup()
        if view is not None:
            self._resize_popup(view)
            self._position_popup_left(view)


class LangComboBox(_AlignComboBox):
    def __init__(self, align_right: bool = False, parent=None):
        alignment = (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            if align_right
            else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        super().__init__(alignment, COMBO_QSS, parent)


class ServiceComboBox(_AlignComboBox):
    def __init__(self, parent=None):
        alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        super().__init__(alignment, SERVICE_COMBO_QSS, parent)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


def apply_rounded_mask(
    widget: QWidget,
    radius: float | None = None,
    *,
    radius_top: float | None = None,
    radius_bottom: float | None = None,
):
    if widget.width() <= 0 or widget.height() <= 0:
        return
    if radius_top is None and radius_bottom is None:
        r = BORDER_RADIUS if radius is None else radius
        radius_top = radius_bottom = r
    elif radius_top is None:
        radius_top = radius if radius is not None else BORDER_RADIUS
    elif radius_bottom is None:
        radius_bottom = radius if radius is not None else BORDER_RADIUS
    path = _rounded_rect_path(QRectF(widget.rect()), radius_top, radius_top, radius_bottom, radius_bottom)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


def _rounded_rect_path(
    rect: QRectF,
    radius_tl: float,
    radius_tr: float,
    radius_br: float,
    radius_bl: float,
) -> QPainterPath:
    path = QPainterPath()
    tl, tr, br, bl = radius_tl, radius_tr, radius_br, radius_bl
    path.moveTo(rect.left() + tl, rect.top())
    path.lineTo(rect.right() - tr, rect.top())
    if tr > 0:
        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + tr)
    else:
        path.lineTo(rect.right(), rect.top())
    path.lineTo(rect.right(), rect.bottom() - br)
    if br > 0:
        path.quadTo(rect.right(), rect.bottom(), rect.right() - br, rect.bottom())
    else:
        path.lineTo(rect.right(), rect.bottom())
    path.lineTo(rect.left() + bl, rect.bottom())
    if bl > 0:
        path.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - bl)
    else:
        path.lineTo(rect.left(), rect.bottom())
    path.lineTo(rect.left(), rect.top() + tl)
    if tl > 0:
        path.quadTo(rect.left(), rect.top(), rect.left() + tl, rect.top())
    else:
        path.lineTo(rect.left(), rect.top())
    path.closeSubpath()
    return path


class RoundedPanel(QFrame):
    def __init__(
        self,
        color: str = "#292929",
        radius: int | None = None,
        radius_top: int | None = None,
        radius_bottom: int | None = None,
        border: str | None = None,
        clip_children: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._color = color
        if radius_top is not None or radius_bottom is not None:
            base = radius if radius is not None else BORDER_RADIUS
            self._radius_top = base if radius_top is None else radius_top
            self._radius_bottom = base if radius_bottom is None else radius_bottom
        else:
            r = BORDER_RADIUS if radius is None else radius
            self._radius_top = r
            self._radius_bottom = r
        self._border = border
        self._clip_children = clip_children
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = _rounded_rect_path(
            rect, self._radius_top, self._radius_top, self._radius_bottom, self._radius_bottom
        )
        painter.fillPath(path, QColor(self._color))
        if self._border:
            painter.setPen(QPen(QColor(self._border)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._clip_children:
            apply_rounded_mask(
                self,
                radius_top=self._radius_top,
                radius_bottom=self._radius_bottom,
            )
        else:
            self.clearMask()


class SplitLineWidget(QWidget):
    dragged = Signal(int)
    drag_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(SPLIT_LINE_BLOCK_HEIGHT)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self._dragging = False
        self._start_y = 0
        self._active = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = "#088fff" if self._active else "#303030"
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        y = self.height() // 2
        painter.drawLine(0, y, self.width(), y)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._active = True
            self._start_y = int(event.globalPosition().y())
            self.grabMouse()
            self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._dragging:
            return
        delta = int(event.globalPosition().y()) - self._start_y
        if delta:
            self._start_y = int(event.globalPosition().y())
            self.dragged.emit(delta)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._active = False
            self.releaseMouse()
            self.update()
            self.drag_finished.emit()
            event.accept()


class ResizeHandleWidget(QWidget):
    resized = Signal(int, int)
    drag_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        self._dragging = False
        self._start_x = 0
        self._start_y = 0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#666666" if not self._dragging else "#088fff")
        for i, offset in enumerate((4, 7, 10)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            x = self.width() - offset
            y = self.height() - offset
            painter.drawEllipse(x - 1, y - 1, 2, 2)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_x = int(event.globalPosition().x())
            self._start_y = int(event.globalPosition().y())
            self.grabMouse()
            self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._dragging:
            return
        delta_x = int(event.globalPosition().x()) - self._start_x
        delta_y = int(event.globalPosition().y()) - self._start_y
        if delta_x or delta_y:
            self._start_x = int(event.globalPosition().x())
            self._start_y = int(event.globalPosition().y())
            self.resized.emit(delta_x, delta_y)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.releaseMouse()
            self.update()
            self.drag_finished.emit()
            event.accept()


class MarkCheckBox(QPushButton):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self.clicked.connect(self._toggle)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        self._checked = checked
        self.update()

    def _toggle(self):
        self._checked = not self._checked
        self.update()
        self.toggled.emit(self._checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        # 勾选时仍保留描边，避免框线消失
        if self._checked:
            painter.setPen(QPen(QColor("#0666cc"), 1))
            painter.setBrush(QBrush(QColor("#088fff")))
            painter.drawRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(4, 8, 6, 11)
            painter.drawLine(6, 11, 12, 4)
        else:
            painter.setPen(QPen(QColor("#666666"), 1))
            painter.setBrush(QBrush(QColor("#292929")))
            painter.drawRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)


class HotkeyEdit(RoundedPanel):
    """快捷键录入：聚焦时通知外部暂停全局热键。"""

    def __init__(self, default_sequence: str = "", on_focus_change=None, parent=None):
        super().__init__(color="#292929", border="#3d3d3d", parent=parent)
        self._on_focus_change = on_focus_change
        self.setFixedSize(180, 32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        layout.setSpacing(0)
        self._editor = QKeySequenceEdit(self)
        self._editor.setMaximumSequenceLength(1)
        self._editor.setClearButtonEnabled(True)
        self._editor.setStyleSheet(INPUT_QSS)
        if default_sequence:
            self._editor.setKeySequence(QKeySequence(default_sequence))
        self._editor.installEventFilter(self)
        layout.addWidget(self._editor)

    def key_sequence(self) -> QKeySequence:
        return self._editor.keySequence()

    def set_key_sequence(self, sequence: str | QKeySequence):
        self._editor.setKeySequence(QKeySequence(sequence))

    def hasFocus(self) -> bool:
        return self._editor.hasFocus() or super().hasFocus()

    def clearFocus(self):
        self._editor.clearFocus()
        super().clearFocus()

    def eventFilter(self, obj, event):
        if obj is self._editor and event.type() in (
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        ):
            if self._on_focus_change is not None:
                QTimer.singleShot(0, self._on_focus_change)
        return super().eventFilter(obj, event)


class ToastTip(QWidget):
    def __init__(self, parent: QWidget, text: str, icon_name: str = "check.svg", duration_ms: int = 2500):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._duration_ms = duration_ms
        self._target_pos = QPoint(0, 0)
        self._hide_group = None

        self.card = QFrame(self)
        self.card.setObjectName("toastCard")
        self.card.setStyleSheet(
            f"""
            QFrame#toastCard {{
                background: #353535;
                border: 1px solid #454545;
                border-radius: {BORDER_RADIUS}px;
            }}
            QLabel {{
                color: #f2f2f2;
                font-size: {FONT_SIZE}px;
                background: transparent;
                border: none;
            }}
            """
        )

        layout = QHBoxLayout(self.card)
        layout.setContentsMargins(WIDGET_MARGIN_H, WIDGET_MARGIN_V, WIDGET_MARGIN_H, WIDGET_MARGIN_V)
        layout.setSpacing(WIDGET_MARGIN_H)

        icon_label = QLabel()
        icon_label.setPixmap(load_pixmap(icon_name, ICON_SIZE, ICON_ACCENT))
        icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)

        text_label = QLabel(text)
        disable_label_selection(text_label)

        max_text_w = 240
        if parent is not None and parent.width() > 0:
            max_text_w = max(160, parent.width() - ICON_SIZE - WIDGET_MARGIN_H * 6)

        # 一行能放下就不换行；超宽才折行
        fm = QFontMetrics(text_label.font())
        one_line_w = fm.horizontalAdvance(text.replace("\n", " "))
        needs_wrap = ("\n" in text) or (one_line_w > max_text_w)
        text_label.setWordWrap(needs_wrap)
        if needs_wrap:
            text_label.setMaximumWidth(max_text_w)
            self.card.setMaximumWidth(max_text_w + ICON_SIZE + WIDGET_MARGIN_H * 4)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(text_label, 1)
        else:
            layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(text_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 130))

    def showEvent(self, event):
        super().showEvent(event)
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        self._center_card()
        self.raise_()
        self._play_show_animation()

    def _center_card(self):
        self.card.adjustSize()
        x = max(0, (self.width() - self.card.width()) // 2)
        y = max(0, (self.height() - self.card.height()) // 2)
        self._target_pos = QPoint(x, y)
        self.card.move(x, y + 12)

    def _play_show_animation(self):
        fade_in = QPropertyAnimation(self._opacity, b"opacity", self)
        fade_in.setDuration(220)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        slide_up = QPropertyAnimation(self.card, b"pos", self)
        slide_up.setDuration(220)
        slide_up.setStartValue(self.card.pos())
        slide_up.setEndValue(self._target_pos)
        slide_up.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade_in)
        group.addAnimation(slide_up)
        group.finished.connect(self._schedule_hide)
        group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _schedule_hide(self):
        QTimer.singleShot(self._duration_ms, self._play_hide_animation)

    def _play_hide_animation(self):
        if self._hide_group is not None:
            return

        fade_out = QPropertyAnimation(self._opacity, b"opacity", self)
        fade_out.setDuration(180)
        fade_out.setStartValue(self._opacity.opacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        slide_down = QPropertyAnimation(self.card, b"pos", self)
        slide_down.setDuration(180)
        slide_down.setStartValue(self.card.pos())
        slide_down.setEndValue(QPoint(self._target_pos.x(), self._target_pos.y() + 8))
        slide_down.setEasingCurve(QEasingCurve.Type.InCubic)

        self._hide_group = QParallelAnimationGroup(self)
        self._hide_group.addAnimation(fade_out)
        self._hide_group.addAnimation(slide_down)
        self._hide_group.finished.connect(self.deleteLater)
        self._hide_group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class ScreenCenterToast(QWidget):
    """无父窗口时：在当前屏幕中心显示提示，到时自动消失。"""

    def __init__(self, text: str, duration_ms: int = 1000, parent=None):
        super().__init__(parent)
        self._duration_ms = max(0, int(duration_ms))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.card = QFrame(self)
        self.card.setObjectName("screenToastCard")
        self.card.setStyleSheet(
            f"""
            QFrame#screenToastCard {{
                background: #353535;
                border: 1px solid #454545;
                border-radius: {BORDER_RADIUS}px;
            }}
            QLabel {{
                color: #f2f2f2;
                font-size: {FONT_SIZE}px;
                background: transparent;
                border: none;
            }}
            """
        )
        layout = QHBoxLayout(self.card)
        layout.setContentsMargins(
            WIDGET_MARGIN_H * 2, WIDGET_MARGIN_V + 2, WIDGET_MARGIN_H * 2, WIDGET_MARGIN_V + 2
        )
        text_label = QLabel(text)
        disable_label_selection(text_label)
        layout.addWidget(text_label)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)

        self.card.adjustSize()
        self.resize(self.card.size())
        self.card.move(0, 0)
        self._place_on_screen()

    def _place_on_screen(self):
        from PySide6.QtWidgets import QApplication

        screen = QApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self._place_on_screen()
        fade_in = QPropertyAnimation(self._opacity, b"opacity", self)
        fade_in.setDuration(160)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_in.finished.connect(
            lambda: QTimer.singleShot(self._duration_ms, self._fade_out)
        )
        fade_in.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _fade_out(self):
        fade_out = QPropertyAnimation(self._opacity, b"opacity", self)
        fade_out.setDuration(160)
        fade_out.setStartValue(self._opacity.opacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_out.finished.connect(self.close)
        fade_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def show_screen_center_toast(text: str, duration_ms: int = 1000) -> ScreenCenterToast:
    tip = ScreenCenterToast(text, duration_ms=duration_ms)
    tip.show()
    tip.raise_()
    return tip
