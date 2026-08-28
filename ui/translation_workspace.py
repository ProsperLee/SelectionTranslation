"""划词翻译 / OCR 翻译共用无边框窗口（右侧翻译面板，可选左侧截图）。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from config import load_config, patch_config
from ui.base_window import FramelessWindow
from ui.constants import (
    DEFAULT_OCR_HEIGHT,
    DEFAULT_OCR_WIDTH,
    DEFAULT_TRANSLATION_HEIGHT,
    DEFAULT_TRANSLATION_WIDTH,
    HEADER_DRAG_HEIGHT,
    MIN_CONTENT_HEIGHT,
    MIN_TEXTAREA_HEIGHT,
    MIN_TRANSLATION_HEIGHT,
    MIN_TRANSLATION_WIDTH,
    SNAPSHOT_WIDTH,
    WIDGET_MARGIN_H,
    WIDGET_MARGIN_V,
)
from ui.screenshot_panel import ScreenshotPanel
from ui.translation_panel import TranslationPanel


class TranslationWorkspace(FramelessWindow):
    """划词翻译 / OCR 翻译共用窗口：右侧均为 TranslationPanel，左侧可选截图区。"""

    _PROFILE_DEFAULTS = {
        "translation": (DEFAULT_TRANSLATION_WIDTH, DEFAULT_TRANSLATION_HEIGHT),
        "ocr": (DEFAULT_OCR_WIDTH, DEFAULT_OCR_HEIGHT),
    }

    def __init__(
        self,
        *,
        title: str,
        with_screenshot: bool,
        default_width: int,
        min_width: int,
        screenshot=None,
        pending_ocr: bool = False,
        pending_selection: bool = False,
        config_profile: str = "translation",
        placement_physical: tuple[int, int] | None = None,
        placement_mode: str = "cursor",
    ):
        super().__init__(show_header=False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(title)
        self._with_screenshot = with_screenshot
        # 划词 / OCR 右侧面板最小宽度一致；窗口最小宽计入边距与截图区
        if with_screenshot:
            self._min_width = max(
                min_width,
                SNAPSHOT_WIDTH + MIN_TRANSLATION_WIDTH + WIDGET_MARGIN_H * 3,
            )
        else:
            self._min_width = max(min_width, MIN_TRANSLATION_WIDTH + WIDGET_MARGIN_H * 2)
        # 左右下留白；翻译区贴顶。OCR 左侧截图单独加顶部边距。
        self.body.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, WIDGET_MARGIN_V)
        self._config_profile = config_profile
        self._default_width, self._default_height = self._PROFILE_DEFAULTS.get(
            config_profile,
            (default_width, MIN_TRANSLATION_HEIGHT),
        )
        self._restore_pinned = False
        self._placement_physical = placement_physical
        self._placement_mode = placement_mode
        self._placement_applied = False

        self.panel = TranslationPanel(show_header=True, embedded=with_screenshot)
        if pending_ocr:
            self.panel.show_recognizing()
        elif pending_selection:
            self.panel.show_capturing()
        self.panel.close_btn.clicked.connect(self.close)
        self.panel.layout_changed.connect(self._on_panel_layout_changed)
        self.panel.set_layout_save_callback(self._save_layout_pref)

        if with_screenshot:
            self.screenshot_panel = ScreenshotPanel(screenshot=screenshot)
            left = QWidget()
            left.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            left_layout = QVBoxLayout(left)
            left_layout.setContentsMargins(0, WIDGET_MARGIN_V, 0, 0)
            left_layout.setSpacing(0)
            left_layout.addWidget(self.screenshot_panel, 1)

            content = QWidget()
            content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            layout = QHBoxLayout(content)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(WIDGET_MARGIN_H)
            layout.addWidget(left, 0)
            layout.addWidget(self.panel, 1)
            self.body.addWidget(content)
            self.panel.setMinimumWidth(MIN_TRANSLATION_WIDTH)
        else:
            wrapper = QWidget()
            wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            layout = QVBoxLayout(wrapper)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(self.panel)
            self.body.addWidget(wrapper)

        self.setMinimumSize(self._min_width, MIN_TRANSLATION_HEIGHT)
        self._apply_layout_config(load_config())
        self._on_panel_layout_changed()
        self.enable_corner_resize(self._on_resize)
        if self._resize_handle is not None:
            self._resize_handle.drag_finished.connect(self._save_window_size)
        # 在 show 之前定位，避免先闪到屏幕默认位置再跳到锚点
        if self._placement_physical is not None:
            self._apply_placement()

    def _layout_width_key(self) -> str:
        return f"{self._config_profile}_width"

    def _layout_height_key(self) -> str:
        return f"{self._config_profile}_height"

    def _body_margin_height(self) -> int:
        m = self.body.contentsMargins()
        return m.top() + m.bottom()

    def _preferred_window_height(self) -> int:
        return self.panel.preferred_height() + self._body_margin_height()

    def _apply_layout_config(self, config: dict):
        try:
            split_ratio = float(config.get("split_ratio", 0.5))
        except (TypeError, ValueError):
            split_ratio = 0.5

        # 引擎 / 语言需在布局回调注册之后恢复，且内部已 blockSignals
        self.panel.apply_preferences(config)

        width = max(
            self._min_width,
            int(config.get(self._layout_width_key(), self._default_width)),
        )
        saved_height = max(
            MIN_TRANSLATION_HEIGHT,
            int(config.get(self._layout_height_key(), self._default_height)),
        )

        # 先按保存的窗口高度算出「输入+结果」总高，再套分栏比例，避免比例被默认高度冲掉
        chrome = self.panel.preferred_height() - (
            self.panel.content_height() + self.panel.textarea_height()
        )
        target_variable = max(
            MIN_TEXTAREA_HEIGHT + MIN_CONTENT_HEIGHT,
            saved_height - self._body_margin_height() - chrome,
        )
        self.panel.apply_split_ratio(split_ratio, total=target_variable)

        height = max(MIN_TRANSLATION_HEIGHT, self._preferred_window_height())
        self.resize(width, height)
        self.setMinimumHeight(height)

        pinned = bool(config.get("window_pinned", False))
        self.panel.set_pinned(pinned)
        self._restore_pinned = pinned

    def showEvent(self, event):
        # 兜底：若构造时未定位成功，在真正显示前同步挪到锚点（不用 singleShot，避免闪一下）
        if not self._placement_applied and self._placement_physical is not None:
            self._apply_placement()
        super().showEvent(event)
        if self._restore_pinned:
            self.set_stays_on_top(True)
            self._restore_pinned = False

    def _apply_placement(self):
        if self._placement_applied or self._placement_physical is None:
            return
        from ui.screen_coords import place_window_near_physical

        px, py = self._placement_physical
        place_window_near_physical(self, px, py, mode=self._placement_mode)
        self._placement_applied = True

    def _save_layout_pref(self, key: str, value):
        patch_config(**{key: value})

    def _save_window_size(self):
        patch_config(
            **{
                self._layout_width_key(): self.width(),
                self._layout_height_key(): self.height(),
            }
        )

    def _header_drag_x_min(self) -> float:
        if not self._with_screenshot:
            return 0
        m = self.body.contentsMargins()
        return m.left() + SNAPSHOT_WIDTH + WIDGET_MARGIN_H

    def _raise_floating_controls(self):
        self.panel.raise_floating_controls()
        if self._with_screenshot:
            self.screenshot_panel.raise_floating_controls()
        super()._raise_floating_controls()

    def _on_panel_layout_changed(self):
        self._sync_window_height()

    def _sync_window_height(self):
        min_h = max(MIN_TRANSLATION_HEIGHT, self._preferred_window_height())
        self.setMinimumHeight(min_h)
        self.resize(self.width(), min_h)

    def _on_resize(self, delta_x: int, delta_y: int):
        next_width = max(self._min_width, self.width() + delta_x)
        next_content = max(MIN_CONTENT_HEIGHT, self.panel.content_height() + delta_y)
        self.panel.apply_content_height(next_content)
        h = self._preferred_window_height()
        self.setMinimumHeight(h)
        self.resize(next_width, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            if pos.y() <= HEADER_DRAG_HEIGHT and pos.x() > self._header_drag_x_min():
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

    def _header_drag_area(self) -> bool:
        return False

    def apply_recognized_text(self, text: str):
        self.panel.set_source_text(text)
        self.panel.show_translating()
        self.panel.run_translate()

    apply_selection_text = apply_recognized_text

    def apply_selection_empty(self):
        self.panel.set_source_text("")
        self.panel.set_result_text(self.panel.empty_selection_hint())

    def apply_ocr_error(self, message: str):
        self.panel.set_source_text("")
        self.panel.set_result_text(message, is_error=True)

    def closeEvent(self, event):
        # 关闭时再写一次尺寸，避免只靠缩放手柄结束才保存
        self._save_window_size()
        self.panel.shutdown_tasks()
        super().closeEvent(event)
