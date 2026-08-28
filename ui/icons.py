from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton

from ui.constants import BORDER_RADIUS, FONT_SIZE, HEADER_BTN_SIZE, ICON_SIZE, ICONS_DIR

ICON_MUTED = "#696969"
ICON_MUTED_HOVER = "#959595"
ICON_MUTED_PRESSED = "#bdbdbd"
ICON_LIGHT = "#e8e8e8"
ICON_LIGHT_HOVER = "#ffffff"
ICON_LIGHT_PRESSED = "#cccccc"
ICON_ON_PRIMARY = "#ffffff"
ICON_ON_PRIMARY_PRESSED = "#dceeff"
ICON_ACCENT = "#088fff"


def icon_path(name: str) -> str:
    return str(ICONS_DIR / name)


def load_pixmap(name: str, size: int = ICON_SIZE, color: str = "#000000") -> QPixmap:
    renderer = QSvgRenderer(icon_path(name))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    return pixmap


def load_icon(name: str, size: int = ICON_SIZE, color: str = "#000000") -> QIcon:
    return QIcon(load_pixmap(name, size, color))


def load_app_icon(color: str = ICON_ACCENT) -> QIcon:
    """应用 / 任务栏图标，与托盘同色同图，多尺寸以适配 DPI。"""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(load_pixmap("translate.svg", size, color))
    return icon


class IconButton(QPushButton):
    _VARIANTS = {
        "muted": {
            "icon": ICON_MUTED,
            "hover_icon": ICON_MUTED_HOVER,
            "pressed_icon": ICON_MUTED_PRESSED,
            "hover_bg": "#303030",
            "pressed_bg": "#3a3a3a",
            "bg": "transparent",
        },
        "light": {
            "icon": ICON_LIGHT,
            "hover_icon": ICON_LIGHT_HOVER,
            "pressed_icon": ICON_LIGHT_PRESSED,
            "hover_bg": "#3a3a3a",
            "pressed_bg": "#454545",
            "bg": "transparent",
        },
        "overlay": {
            "icon": ICON_ON_PRIMARY,
            "hover_icon": ICON_ON_PRIMARY,
            "pressed_icon": ICON_ON_PRIMARY_PRESSED,
            "hover_bg": "rgba(0, 0, 0, 0.75)",
            "pressed_bg": "rgba(0, 0, 0, 0.85)",
            "bg": "rgba(0, 0, 0, 0.55)",
        },
    }

    def __init__(
        self,
        icon_name: str,
        size: int = ICON_SIZE,
        variant: str = "muted",
        button_size: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = size
        self._variant = variant
        self._state = "normal"
        self._active = False
        self._palette = self._VARIANTS[variant]
        btn_size = button_size if button_size is not None else max(size + 12, HEADER_BTN_SIZE)
        self.setFixedSize(btn_size, btn_size)
        self.setIconSize(QSize(size, size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply_state("normal")

    def set_active(self, active: bool):
        self._active = active
        self._apply_state(self._state if self._state != "normal" or active else "normal")

    def _apply_state(self, state: str):
        self._state = state
        if self._active and state == "normal":
            icon_color = ICON_ACCENT
            bg = "transparent"
        elif state == "pressed":
            icon_color = self._palette["pressed_icon"]
            bg = self._palette["pressed_bg"]
        elif state == "hover":
            icon_color = self._palette["hover_icon"]
            bg = self._palette["hover_bg"]
        else:
            icon_color = self._palette["icon"]
            bg = self._palette["bg"]

        self.setIcon(load_icon(self._icon_name, self._icon_size, icon_color))
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: {BORDER_RADIUS}px;
            }}
            """
        )

    def enterEvent(self, event):
        if self._state != "pressed":
            self._apply_state("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_state("normal")
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._apply_state("pressed")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)
        if self.rect().contains(event.position().toPoint()):
            self._apply_state("hover")
        else:
            self._apply_state("normal")


class PrimaryIconButton(QPushButton):
    def __init__(self, icon_name: str, text: str, icon_size: int = ICON_SIZE, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = icon_size
        self.setText(text)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply_style("normal")

    def _apply_style(self, state: str):
        if state == "pressed":
            bg = "#006acc"
            icon_color = ICON_ON_PRIMARY_PRESSED
        elif state == "hover":
            bg = "#0078e6"
            icon_color = ICON_ON_PRIMARY
        else:
            bg = "#088fff"
            icon_color = ICON_ON_PRIMARY

        self.setIcon(load_icon(self._icon_name, self._icon_size, icon_color))
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: {BORDER_RADIUS}px;
                color: #ffffff;
                font-size: {FONT_SIZE}px;
                padding: 3px 8px;
            }}
            """
        )

    def enterEvent(self, event):
        self._apply_style("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style("normal")
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._apply_style("pressed")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)
        if self.rect().contains(event.position().toPoint()):
            self._apply_style("hover")
        else:
            self._apply_style("normal")


class PrimaryButton(QPushButton):
    def __init__(self, text: str, icon_name: str | None = None, icon_size: int = ICON_SIZE, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = icon_size
        self.setText(text)
        if icon_name:
            self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._apply_style("normal")

    def _apply_style(self, state: str):
        if state == "pressed":
            bg = "#006acc"
            icon_color = ICON_ON_PRIMARY_PRESSED
        elif state == "hover":
            bg = "#0078e6"
            icon_color = ICON_ON_PRIMARY
        else:
            bg = "#088fff"
            icon_color = ICON_ON_PRIMARY

        if self._icon_name:
            self.setIcon(load_icon(self._icon_name, self._icon_size, icon_color))
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {bg};
                border: none;
                border-radius: {BORDER_RADIUS}px;
                color: #ffffff;
                font-size: {FONT_SIZE}px;
                padding: 0 14px;
            }}
            """
        )

    def enterEvent(self, event):
        self._apply_style("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style("normal")
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._apply_style("pressed")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)
        if self.rect().contains(event.position().toPoint()):
            self._apply_style("hover")
        else:
            self._apply_style("normal")
