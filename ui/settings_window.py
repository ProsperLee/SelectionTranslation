from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from boot import reconcile_start_on_boot, set_start_on_boot
from config import (
    acquire_settings_lock,
    load_config,
    normalize_hotkey,
    release_settings_lock,
    save_config,
)
from ui.base_window import FramelessWindow
from ui.constants import (
    DEFAULT_SETTINGS_WIDTH,
    FONT_SIZE,
    HEADER_BTN_SIZE,
    WIDGET_MARGIN_H,
    WIDGET_MARGIN_V,
)
from ui.icons import IconButton, PrimaryButton
from ui.text_utils import disable_label_selection
from ui.widgets import HotkeyEdit, MarkCheckBox, ToastTip


class SettingsWindow(FramelessWindow):
    config_saved = Signal()

    def __init__(self):
        super().__init__(show_header_border=True)
        self.setFixedWidth(DEFAULT_SETTINGS_WIDTH)
        self.resize(DEFAULT_SETTINGS_WIDTH, 360)
        self._config = load_config()
        self._build_content()

    def showEvent(self, event):
        super().showEvent(event)
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._reload_from_config()

    def hideEvent(self, event):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        release_settings_lock()
        super().hideEvent(event)

    def _reload_from_config(self):
        """每次显示时从磁盘刷新，并与注册表开机自启对齐。"""
        reconcile_start_on_boot()
        self._config = load_config()
        self.hotkey_edit.set_key_sequence(
            normalize_hotkey(self._config.get("hotkey", ""))
        )
        self.ocr_hotkey_edit.set_key_sequence(
            normalize_hotkey(self._config.get("ocr_hotkey", ""))
        )
        self.color_picker_hotkey_edit.set_key_sequence(
            normalize_hotkey(self._config.get("color_picker_hotkey", ""))
        )
        self.sticky_note_hotkey_edit.set_key_sequence(
            normalize_hotkey(self._config.get("sticky_note_hotkey", ""))
        )
        self.startup_checkbox.setChecked(bool(self._config.get("start_on_boot", False)))
        self.selection_button_checkbox.setChecked(
            bool(self._config.get("selection_bubble", False))
        )

    def _build_content(self):
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        title = QLabel("设置")
        disable_label_selection(title)
        title.setStyleSheet(f"color: #ffffff; font-size: {FONT_SIZE}px; background: transparent;")
        self.close_btn = IconButton(
            "close.svg", variant="light", button_size=HEADER_BTN_SIZE
        )
        self.close_btn.clicked.connect(self.close)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.close_btn)
        self.set_header_layout(header_layout)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(WIDGET_MARGIN_H, WIDGET_MARGIN_V, WIDGET_MARGIN_H, WIDGET_MARGIN_V)
        main_layout.setSpacing(WIDGET_MARGIN_V)

        self.hotkey_edit = HotkeyEdit(
            normalize_hotkey(self._config["hotkey"]),
            on_focus_change=self._sync_hotkey_capture_lock,
        )
        self._add_row(main_layout, "划词快捷键", self.hotkey_edit)

        self.ocr_hotkey_edit = HotkeyEdit(
            normalize_hotkey(self._config["ocr_hotkey"]),
            on_focus_change=self._sync_hotkey_capture_lock,
        )
        self._add_row(main_layout, "OCR快捷键", self.ocr_hotkey_edit)

        self.color_picker_hotkey_edit = HotkeyEdit(
            normalize_hotkey(self._config.get("color_picker_hotkey", "Ctrl+Alt+I")),
            on_focus_change=self._sync_hotkey_capture_lock,
        )
        self._add_row(main_layout, "吸色快捷键", self.color_picker_hotkey_edit)

        self.sticky_note_hotkey_edit = HotkeyEdit(
            normalize_hotkey(self._config.get("sticky_note_hotkey", "Ctrl+Alt+N")),
            on_focus_change=self._sync_hotkey_capture_lock,
        )
        self._add_row(main_layout, "便签快捷键", self.sticky_note_hotkey_edit)

        self.startup_checkbox = MarkCheckBox(checked=bool(self._config.get("start_on_boot", False)))
        self._add_row(main_layout, "开机自启", self.startup_checkbox)
        self.selection_button_checkbox = MarkCheckBox(
            checked=bool(self._config.get("selection_bubble", False))
        )
        self._add_row(main_layout, "划词按钮", self.selection_button_checkbox)
        self.body.addWidget(main)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(WIDGET_MARGIN_H, WIDGET_MARGIN_V, WIDGET_MARGIN_H, WIDGET_MARGIN_V)
        footer_layout.addStretch()
        save_btn = PrimaryButton("保存", "save.svg")
        save_btn.clicked.connect(self._save)
        footer_layout.addWidget(save_btn)
        self.body.addWidget(footer)

    def _add_row(self, layout: QVBoxLayout, label_text: str, field: QWidget):
        row = QWidget()
        row.setMinimumHeight(36)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(WIDGET_MARGIN_H)
        label = QLabel(label_text)
        disable_label_selection(label)
        label.setFixedWidth(84)
        label.setStyleSheet(f"color: #ffffff; font-size: {FONT_SIZE}px;")
        row_layout.addWidget(label)
        row_layout.addWidget(field, 0, Qt.AlignmentFlag.AlignLeft)
        row_layout.addStretch()
        layout.addWidget(row)

    def _hotkey_edit_contains(self, widget) -> bool:
        while widget is not None:
            if widget in (
                self.hotkey_edit,
                self.ocr_hotkey_edit,
                self.color_picker_hotkey_edit,
                self.sticky_note_hotkey_edit,
            ):
                return True
            if widget is self:
                break
            widget = widget.parentWidget()
        return False

    def eventFilter(self, obj, event):
        from PySide6.QtWidgets import QApplication

        if (
            event.type() == QEvent.Type.MouseButtonPress
            and self.isVisible()
            and self.isActiveWindow()
        ):
            target = QApplication.widgetAt(event.globalPosition().toPoint())
            if target is not None and not self._hotkey_edit_contains(target):
                if self.hotkey_edit.hasFocus():
                    self.hotkey_edit.clearFocus()
                if self.ocr_hotkey_edit.hasFocus():
                    self.ocr_hotkey_edit.clearFocus()
                if self.color_picker_hotkey_edit.hasFocus():
                    self.color_picker_hotkey_edit.clearFocus()
                if self.sticky_note_hotkey_edit.hasFocus():
                    self.sticky_note_hotkey_edit.clearFocus()
        return super().eventFilter(obj, event)

    def _sync_hotkey_capture_lock(self):
        if (
            self.hotkey_edit.hasFocus()
            or self.ocr_hotkey_edit.hasFocus()
            or self.color_picker_hotkey_edit.hasFocus()
            or self.sticky_note_hotkey_edit.hasFocus()
        ):
            acquire_settings_lock()
        else:
            release_settings_lock()

    def _save(self):
        hotkey = normalize_hotkey(
            self.hotkey_edit.key_sequence().toString(QKeySequence.SequenceFormat.NativeText)
        )
        ocr_hotkey = normalize_hotkey(
            self.ocr_hotkey_edit.key_sequence().toString(QKeySequence.SequenceFormat.NativeText)
        )
        color_picker_hotkey = normalize_hotkey(
            self.color_picker_hotkey_edit.key_sequence().toString(
                QKeySequence.SequenceFormat.NativeText
            )
        )
        sticky_note_hotkey = normalize_hotkey(
            self.sticky_note_hotkey_edit.key_sequence().toString(
                QKeySequence.SequenceFormat.NativeText
            )
        )
        if not hotkey:
            QMessageBox.warning(self, "快捷键无效", "请设置划词翻译快捷键。")
            return
        if not ocr_hotkey:
            QMessageBox.warning(self, "快捷键无效", "请设置 OCR 快捷键。")
            return
        if not color_picker_hotkey:
            QMessageBox.warning(self, "快捷键无效", "请设置吸色快捷键。")
            return
        if not sticky_note_hotkey:
            QMessageBox.warning(self, "快捷键无效", "请设置便签快捷键。")
            return
        keys = [
            hotkey.casefold(),
            ocr_hotkey.casefold(),
            color_picker_hotkey.casefold(),
            sticky_note_hotkey.casefold(),
        ]
        if len(set(keys)) != len(keys):
            QMessageBox.warning(self, "快捷键冲突", "各项快捷键不能相同。")
            return

        self._config = {
            **load_config(),
            "hotkey": hotkey,
            "ocr_hotkey": ocr_hotkey,
            "color_picker_hotkey": color_picker_hotkey,
            "sticky_note_hotkey": sticky_note_hotkey,
            "start_on_boot": self.startup_checkbox.isChecked(),
            "selection_bubble": self.selection_button_checkbox.isChecked(),
        }
        save_config(self._config)
        set_start_on_boot(bool(self._config["start_on_boot"]))
        release_settings_lock()
        self.config_saved.emit()
        toast = ToastTip(self, "设置已保存", duration_ms=1000)
        toast.show()

    def _header_drag_area(self) -> bool:
        return True
