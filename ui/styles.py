from ui.constants import (
    BORDER_RADIUS,
    COMBO_POPUP_FONT_SIZE,
    COMBO_POPUP_ROW_HEIGHT,
    FONT_SIZE,
    ICONS_DIR,
    ICON_SIZE,
    WIDGET_MARGIN_H,
    WIDGET_MARGIN_V,
)

R = BORDER_RADIUS
_CHEVRON_ICON = (ICONS_DIR / "chevron_down.svg").as_posix().replace("\\", "/")

COMBO_POPUP_VIEW_QSS = f"""
QComboBox QAbstractItemView {{
    background: #1e1e1e;
    color: #d4d4d4;
    border: none;
    border-radius: {R}px;
    padding: {WIDGET_MARGIN_V // 2}px {WIDGET_MARGIN_H}px;
    outline: none;
    font-size: {COMBO_POPUP_FONT_SIZE}px;
    selection-background-color: transparent;
}}
QComboBox QAbstractItemView::item {{
    min-height: {COMBO_POPUP_ROW_HEIGHT}px;
    height: {COMBO_POPUP_ROW_HEIGHT}px;
    padding: 0 {WIDGET_MARGIN_H}px;
    border: none;
    background: transparent;
    font-size: {COMBO_POPUP_FONT_SIZE}px;
}}
QComboBox QAbstractItemView::item:selected {{
    background: transparent;
    color: #ffffff;
}}
QComboBox QAbstractItemView::item:hover {{
    background: transparent;
}}
"""

COMBO_POPUP_LIST_QSS = f"""
QAbstractItemView {{
    background: #1e1e1e;
    color: #d4d4d4;
    border: none;
    border-radius: {R}px;
    padding: {WIDGET_MARGIN_V // 2}px {WIDGET_MARGIN_H}px;
    outline: none;
    font-size: {COMBO_POPUP_FONT_SIZE}px;
    selection-background-color: transparent;
}}
QAbstractItemView::item {{
    min-height: {COMBO_POPUP_ROW_HEIGHT}px;
    height: {COMBO_POPUP_ROW_HEIGHT}px;
    padding: 0 {WIDGET_MARGIN_H}px;
    border: none;
    background: transparent;
    font-size: {COMBO_POPUP_FONT_SIZE}px;
}}
QAbstractItemView::item:selected {{
    background: transparent;
    color: #ffffff;
}}
QAbstractItemView::item:hover {{
    background: transparent;
}}
"""

SCROLLBAR_QSS = f"""
QScrollBar:vertical {{
    width: 6px;
    background: transparent;
    margin: {WIDGET_MARGIN_V}px 0;
}}
QScrollBar::handle:vertical {{
    background: #555555;
    border: 1px solid transparent;
    border-radius: 999px;
    min-height: 24px;
    margin: 0 1px;
}}
QScrollBar::handle:vertical:hover {{
    background: #666666;
}}
QScrollBar::handle:vertical:pressed {{
    background: #088fff;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    height: 6px;
    background: transparent;
    margin: 0 {WIDGET_MARGIN_H}px;
}}
QScrollBar::handle:horizontal {{
    background: #555555;
    border: 1px solid transparent;
    border-radius: 999px;
    min-width: 24px;
    margin: 1px 0;
}}
QScrollBar::handle:horizontal:hover {{
    background: #666666;
}}
QScrollBar::handle:horizontal:pressed {{
    background: #088fff;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: none;
}}
"""

def note_scrollbar_qss(*, dark_bg: bool) -> str:
    """ä¾¿ç­¾æ»å¨æ¡ï¼æµåºç¨æ·±è²æ»åï¼æ·±åºç¨æµè²æ»åã"""
    handle = "rgba(255, 255, 255, 70)" if dark_bg else "rgba(0, 0, 0, 55)"
    handle_hover = "rgba(255, 255, 255, 120)" if dark_bg else "rgba(0, 0, 0, 90)"
    return f"""
QScrollBar:vertical {{
    width: 6px;
    background: transparent;
    margin: {WIDGET_MARGIN_V}px 0;
}}
QScrollBar::handle:vertical {{
    background: {handle};
    border: 1px solid transparent;
    border-radius: 999px;
    min-height: 24px;
    margin: 0 1px;
}}
QScrollBar::handle:vertical:hover {{
    background: {handle_hover};
}}
QScrollBar::handle:vertical:pressed {{
    background: #088fff;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    height: 6px;
    background: transparent;
    margin: 0 {WIDGET_MARGIN_H}px;
}}
QScrollBar::handle:horizontal {{
    background: {handle};
    border: 1px solid transparent;
    border-radius: 999px;
    min-width: 24px;
    margin: 1px 0;
}}
QScrollBar::handle:horizontal:hover {{
    background: {handle_hover};
}}
QScrollBar::handle:horizontal:pressed {{
    background: #088fff;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: none;
}}
"""


def note_text_edit_qss(*, text_color: str) -> str:
    return f"""
QPlainTextEdit {{
    background: transparent;
    border: none;
    color: {text_color};
    font-size: {FONT_SIZE}px;
    padding: {WIDGET_MARGIN_H}px;
}}
QPlainTextEdit QWidget {{
    background: transparent;
}}
"""


# é»è®¤æµè²ä¾¿ç­¾æ ·å¼ï¼å¼å®¹æ§å¼ç¨ï¼
NOTE_SCROLLBAR_QSS = note_scrollbar_qss(dark_bg=False)
NOTE_TEXT_EDIT_QSS = note_text_edit_qss(text_color="#333333")

COMBO_QSS = f"""
QComboBox {{
    background: transparent;
    border: none;
    color: #f2f2f2;
    font-size: {FONT_SIZE}px;
    padding: 0 {WIDGET_MARGIN_H}px;
}}
QComboBox::drop-down {{
    border: none;
    width: 0;
}}
{COMBO_POPUP_VIEW_QSS}
"""

SERVICE_COMBO_QSS = f"""
QComboBox {{
    background: transparent;
    border: none;
    color: #f2f2f2;
    font-size: {FONT_SIZE}px;
    padding: 0;
    spacing: 2px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: {ICON_SIZE}px;
    border: none;
    padding: 0;
    margin: 0;
}}
QComboBox::down-arrow {{
    image: url({_CHEVRON_ICON});
    width: {ICON_SIZE}px;
    height: {ICON_SIZE}px;
}}
{COMBO_POPUP_VIEW_QSS}
"""

TEXT_EDIT_QSS = f"""
QPlainTextEdit {{
    background: #292929;
    border: none;
    color: #f2f2f2;
    font-size: {FONT_SIZE}px;
    padding: {WIDGET_MARGIN_V}px {WIDGET_MARGIN_H}px;
}}
QPlainTextEdit QWidget {{
    background: #292929;
}}
"""

RESULT_EDIT_QSS = f"""
QTextEdit {{
    background: #292929;
    border: none;
    color: #f2f2f2;
    font-size: {FONT_SIZE}px;
    padding: {WIDGET_MARGIN_V}px {WIDGET_MARGIN_H}px;
}}
QTextEdit QWidget {{
    background: #292929;
}}
"""

INPUT_QSS = f"""
QLineEdit {{
    background: transparent;
    border: none;
    color: #ffffff;
    font-size: {FONT_SIZE}px;
}}
"""

DARK_TOOLTIP_QSS = """
QToolTip {
    font-size: 12px;
    font-family: "Microsoft YaHei UI";
    padding: 4px 8px;
    color: #e8e8e8;
    background-color: #2d2d2d;
    border: 1px solid #454545;
    border-radius: 4px;
}
"""


def ensure_dark_tooltip_style() -> None:
    """QToolTip 是独立顶层窗，样式须挂在 QApplication 上。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    sheet = app.styleSheet() or ""
    if "QToolTip {" in sheet:
        return
    app.setStyleSheet(sheet + DARK_TOOLTIP_QSS)
