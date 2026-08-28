from PySide6.QtCore import QEvent, Qt, QTimer, QSize, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from translate_task import TranslateTask
from translator import extract_primary_translation, rich_result_to_html
from ui.constants import (
    BORDER_RADIUS,
    DEFAULT_CONTENT_HEIGHT,
    DEFAULT_TEXTAREA_HEIGHT,
    FONT_SIZE,
    HEADER_BAR_HEIGHT,
    HEADER_BTN_SIZE,
    MIN_CONTENT_HEIGHT,
    MIN_TEXTAREA_HEIGHT,
    MIN_TRANSLATION_WIDTH,
    RESULT_HEADER_HEIGHT,
    SPLIT_LINE_BLOCK_HEIGHT,
    TAG_DOT_SIZE,
    TAG_MARGIN_H,
    TAG_MARGIN_V,
    WIDGET_MARGIN_H,
    WIDGET_MARGIN_V,
)
from ui.languages import detect_language_label, display_to_code, sync_language_combos
from ui.translation_services import ENGINE_ITEMS, engine_api_code, normalize_engine
from ui.icons import IconButton, PrimaryIconButton
from ui.styles import RESULT_EDIT_QSS, SCROLLBAR_QSS, TEXT_EDIT_QSS
from ui.text_utils import disable_label_selection, enable_readonly_textarea_selection, enable_textarea_selection
from ui.widgets import LangComboBox, RoundedPanel, ServiceComboBox, SplitLineWidget


def _label(text: str) -> QLabel:
    label = QLabel(text)
    disable_label_selection(label)
    return label


EMPTY_SELECTION_HINT = (
    "未检测到选中文本。可重新划选后按快捷键；"
    "若应用不支持无障碍接口，可先手动复制再按快捷键，或改用 OCR。"
)

_BUSY_INPUT_TEXTS = frozenset({"正在识别...", "正在获取选中文本..."})
_LANG_DETECT_DEBOUNCE_MS = 350


class LanguageTag(QWidget):
    def __init__(self, text: str = "英语", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(TAG_MARGIN_H, TAG_MARGIN_V, TAG_MARGIN_H, TAG_MARGIN_V)
        layout.setSpacing(TAG_MARGIN_H)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        dot = QLabel()
        dot.setFixedSize(TAG_DOT_SIZE, TAG_DOT_SIZE)
        dot.setStyleSheet(
            f"background: #088fff; border-radius: {TAG_DOT_SIZE // 2}px;"
        )
        label = _label(text)
        label.setStyleSheet(f"color: #9e9e9e; font-size: {FONT_SIZE}px; background: transparent; border: none;")
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        self._text_label = label
        self.setStyleSheet(
            "LanguageTag {"
            " border: 1px solid #555555;"
            f" border-radius: {BORDER_RADIUS}px;"
            " background: transparent;"
            "}"
        )

    def sizeHint(self):
        return self.minimumSizeHint()

    def set_text(self, text: str):
        self._text_label.setText(text)
        self.updateGeometry()
        self.adjustSize()


class TranslationPanel(QWidget):
    layout_changed = Signal()

    def __init__(self, show_header: bool = True, embedded: bool = False, parent=None):
        super().__init__(parent)
        self._textarea_height = DEFAULT_TEXTAREA_HEIGHT
        self._content_height = DEFAULT_CONTENT_HEIGHT
        self._show_header = show_header
        self._embedded = embedded
        self._pinned = False
        self._layout_save_callback = None
        self._translate_task: TranslateTask | None = None
        self._translate_generation = 0
        self._auto_translate_guard = False
        self._result_copy_text = ""
        self._result_full_text = ""
        self._detect_timer = QTimer(self)
        self._detect_timer.setSingleShot(True)
        self._detect_timer.setInterval(_LANG_DETECT_DEBOUNCE_MS)
        self._detect_timer.timeout.connect(self._update_detected_lang_tag)
        if embedded:
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet("TranslationPanel { background-color: #212121; }")
        self._build_ui()
        self._bind_events()
        self._sync_panel_size_policy()

    def _sync_panel_size_policy(self):
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        if self._embedded:
            policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        self.setSizePolicy(policy)
        self.setFixedHeight(self.preferred_height())
        self.updateGeometry()

    def sizeHint(self):
        width = max(MIN_TRANSLATION_WIDTH, super().sizeHint().width()) if self._embedded else super().sizeHint().width()
        return QSize(width, self.preferred_height())

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if self._show_header:
            header = QWidget()
            header.setFixedHeight(HEADER_BAR_HEIGHT)
            header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(0)
            self.pin_btn = IconButton(
                "pin.svg", variant="muted", button_size=HEADER_BTN_SIZE
            )
            self.close_btn = IconButton(
                "close.svg", variant="muted", button_size=HEADER_BTN_SIZE
            )
            header_layout.addWidget(
                self.pin_btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            header_layout.addStretch(1)
            header_layout.addWidget(
                self.close_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._header = header
            root.addWidget(header)

        self._main = QWidget()
        self._main.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        main_layout = QVBoxLayout(self._main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        text_wrap = RoundedPanel("#292929")
        text_layout = QVBoxLayout(text_wrap)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        self.textarea = QPlainTextEdit()
        self.textarea.setPlaceholderText("请输入要翻译的文本")
        self.textarea.setFixedHeight(self._textarea_height)
        self.textarea.setStyleSheet(TEXT_EDIT_QSS + SCROLLBAR_QSS)
        self.textarea.setFrameShape(QFrame.Shape.NoFrame)
        enable_textarea_selection(self.textarea)
        text_layout.addWidget(self.textarea)

        tool = QWidget()
        tool.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        tool_layout = QHBoxLayout(tool)
        tool_layout.setContentsMargins(WIDGET_MARGIN_H, WIDGET_MARGIN_V, WIDGET_MARGIN_H, WIDGET_MARGIN_V)
        tool_layout.setSpacing(WIDGET_MARGIN_H)
        self.copy_input_btn = IconButton("copy.svg", variant="light")
        self.lang_tag = LanguageTag("检测中...")
        tool_layout.addWidget(self.copy_input_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        tool_layout.addWidget(self.lang_tag, 0, Qt.AlignmentFlag.AlignVCenter)
        tool_layout.addStretch()
        self.translate_btn = PrimaryIconButton("translate.svg", "翻译")
        tool_layout.addWidget(self.translate_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        text_layout.addWidget(tool)
        main_layout.addWidget(text_wrap)
        main_layout.addSpacing(WIDGET_MARGIN_V)

        lang_wrap = RoundedPanel("#303030")
        lang_layout = QHBoxLayout(lang_wrap)
        lang_layout.setContentsMargins(WIDGET_MARGIN_H, WIDGET_MARGIN_V, WIDGET_MARGIN_H, WIDGET_MARGIN_V)
        lang_layout.setSpacing(0)
        self.source_lang = LangComboBox(align_right=False)
        self.swap_btn = IconButton("swap.svg", variant="light")
        self.target_lang = LangComboBox(align_right=True)
        lang_layout.addWidget(self.source_lang, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lang_layout.addWidget(self.swap_btn, 0, Qt.AlignmentFlag.AlignCenter)
        lang_layout.addWidget(self.target_lang, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(lang_wrap)

        self.split_line = SplitLineWidget()
        main_layout.addWidget(self.split_line)

        result_wrap = RoundedPanel("#292929")
        result_layout = QVBoxLayout(result_wrap)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(0)

        result_header = QWidget()
        result_header.setFixedHeight(RESULT_HEADER_HEIGHT)
        result_header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        result_header.setStyleSheet("background-color: #303030;")
        result_header_layout = QHBoxLayout(result_header)
        result_header_layout.setContentsMargins(WIDGET_MARGIN_H, 0, WIDGET_MARGIN_H, 0)
        result_header_layout.setSpacing(WIDGET_MARGIN_H)
        self.service_label = _label("自动选择")
        self.service_label.setStyleSheet(f"color: #8f8f8f; font-size: {FONT_SIZE}px; background: transparent;")
        self.copy_result_btn = IconButton("copy.svg", variant="light")
        self.service_combo = ServiceComboBox()
        self.service_combo.addItems(ENGINE_ITEMS)
        self._set_combo_text(self.service_combo, ENGINE_ITEMS[0])
        result_header_layout.addWidget(self.service_label)
        result_header_layout.addWidget(self.copy_result_btn)
        result_header_layout.addStretch()
        result_header_layout.addWidget(
            self.service_combo, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        result_layout.addWidget(result_header)

        self.result_content = QTextEdit()
        self._apply_result_content_height()
        self.result_content.setStyleSheet(RESULT_EDIT_QSS + SCROLLBAR_QSS)
        self.result_content.setFrameShape(QFrame.Shape.NoFrame)
        self.result_content.document().setDocumentMargin(0)
        enable_readonly_textarea_selection(self.result_content)
        result_layout.addWidget(self.result_content)
        main_layout.addWidget(result_wrap)

        root.addWidget(self._main)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.raise_floating_controls()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_floating_controls()

    def raise_floating_controls(self):
        # 仅保证标题栏在内容区之上；工具栏按钮在布局内，无需额外 raise。
        if self._show_header:
            self._main.lower()
            self._header.raise_()
            self.pin_btn.raise_()
            self.close_btn.raise_()

    def _bind_events(self):
        if self._show_header:
            self.pin_btn.clicked.connect(self._toggle_pin)
        self.split_line.dragged.connect(self._on_split_dragged)
        self.split_line.drag_finished.connect(self._on_split_drag_finished)
        self.copy_input_btn.clicked.connect(lambda: self._copy_text(self.textarea.toPlainText()))
        self.copy_result_btn.clicked.connect(self._copy_result)
        self.translate_btn.clicked.connect(self._on_translate)
        self.swap_btn.clicked.connect(self._swap_languages)
        self.service_combo.currentTextChanged.connect(self._on_service_changed)
        self.source_lang.currentTextChanged.connect(self._on_source_lang_changed)
        self.target_lang.currentTextChanged.connect(self._on_target_lang_changed)
        self.textarea.textChanged.connect(self._schedule_lang_detect)
        self.textarea.installEventFilter(self)

    @staticmethod
    def _set_combo_text(combo, text: str):
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentText(text)

    def apply_preferences(self, config: dict):
        engine = normalize_engine(str(config.get("engine", ENGINE_ITEMS[0])))
        source = str(config.get("source_lang", "自动检测"))
        target = str(config.get("target_lang", "英语"))
        engine_api = engine_api_code(engine)

        self.service_combo.blockSignals(True)
        try:
            self._set_combo_text(self.service_combo, engine)
        finally:
            self.service_combo.blockSignals(False)

        sync_language_combos(
            self.source_lang,
            self.target_lang,
            engine_api,
            source_label=source,
            target_label=target,
        )
        self._update_service_label(engine)
        self._update_detected_lang_tag()

    def _update_service_label(self, service: str | None = None):
        name = service or self.service_combo.currentText()
        self.service_label.setText(normalize_engine(name))

    def _on_service_changed(self, text: str):
        engine = normalize_engine(text)
        engine_api = engine_api_code(engine)
        self._update_service_label(engine)
        sync_language_combos(self.source_lang, self.target_lang, engine_api)
        self._update_detected_lang_tag()
        if self._layout_save_callback is not None:
            self._layout_save_callback("engine", engine)
        self._maybe_auto_translate()

    def _on_source_lang_changed(self, text: str):
        if self._layout_save_callback is not None and text:
            self._layout_save_callback("source_lang", text)
        self._update_detected_lang_tag()
        if not self._auto_translate_guard:
            self._maybe_auto_translate()

    def _on_target_lang_changed(self, text: str):
        if self._layout_save_callback is not None and text:
            self._layout_save_callback("target_lang", text)
        if not self._auto_translate_guard:
            self._maybe_auto_translate()

    def eventFilter(self, obj, event):
        if obj is self.textarea and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                self._on_translate()
                return True
        return super().eventFilter(obj, event)

    def _schedule_lang_detect(self):
        self._detect_timer.start()

    def _update_detected_lang_tag(self):
        if self.source_lang.currentText() == "自动检测":
            text = self.textarea.toPlainText()
            if text.strip() in _BUSY_INPUT_TEXTS:
                self.lang_tag.set_text("检测中...")
            else:
                self.lang_tag.set_text(detect_language_label(text))
        else:
            label = self.source_lang.currentText()
            self.lang_tag.set_text(label or "检测中...")

    def _can_translate(self) -> bool:
        source_text = self.textarea.toPlainText().strip()
        return bool(source_text) and source_text not in _BUSY_INPUT_TEXTS

    def _maybe_auto_translate(self):
        if self._auto_translate_guard or not self._can_translate():
            return
        self._on_translate()

    def _copy_text(self, text: str):
        if text.strip():
            QGuiApplication.clipboard().setText(text.strip())

    def _copy_result(self):
        """复制核心译文：单词只复制释义主文，句子只复制句子，不含例句/来源。"""
        text = self._result_copy_text or extract_primary_translation(self._result_full_text)
        self._copy_text(text)

    def _on_translate(self):
        if not self._can_translate():
            return

        source_text = self.textarea.toPlainText().strip()
        self._translate_generation += 1
        generation = self._translate_generation

        engine_api = engine_api_code(normalize_engine(self.service_combo.currentText()))
        source_code = display_to_code(
            self.source_lang.currentText(),
            engine_api,
            allow_auto=True,
            fallback="zh-CN",
        )
        target_code = display_to_code(
            self.target_lang.currentText(),
            engine_api,
            allow_auto=False,
            fallback="en",
        )

        self.show_translating()
        self.translate_btn.setEnabled(False)
        prev = self._translate_task
        if prev is not None:
            try:
                prev.finished_ok.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                prev.failed.disconnect()
            except (TypeError, RuntimeError):
                pass
            prev.requestInterruption()
        from PySide6.QtWidgets import QApplication

        # 挂到应用对象，避免窗口关闭 / GC 时线程仍在跑却被销毁
        task = TranslateTask(
            source_text,
            source_code,
            target_code,
            engine_api,
            QApplication.instance(),
        )
        task.finished_ok.connect(lambda result: self._on_translate_ok(result, generation))
        task.failed.connect(lambda message: self._on_translate_failed(message, generation))
        task.finished.connect(self._on_translate_task_finished)
        self._translate_task = task
        task.start()

    def _on_translate_ok(self, result: str, generation: int):
        if generation != self._translate_generation:
            return
        self.set_result_text(result)
        self.translate_btn.setEnabled(True)

    def _on_translate_failed(self, message: str, generation: int):
        if generation != self._translate_generation:
            return
        self.set_result_text(f"翻译失败：{message}", is_error=True)
        self.translate_btn.setEnabled(True)

    def _on_translate_task_finished(self):
        task = self.sender()
        if task is self._translate_task:
            self._translate_task = None
        if isinstance(task, TranslateTask):
            task.deleteLater()

    def shutdown_tasks(self):
        """窗口关闭前停掉翻译线程，避免 QThread destroyed while still running。"""
        self._translate_generation += 1
        self._detect_timer.stop()
        task = self._translate_task
        self._translate_task = None
        if task is None:
            return
        try:
            task.finished_ok.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            task.failed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            task.finished.disconnect(self._on_translate_task_finished)
        except (TypeError, RuntimeError):
            pass
        task.requestInterruption()
        if task.isRunning() and not task.wait(5000):
            # 仍在跑：挂到 QApplication，结束后再回收，避免无引用被 GC 毁掉
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                task.setParent(app)
            task.finished.connect(task.deleteLater)
            return
        task.deleteLater()
        self.translate_btn.setEnabled(True)

    def show_recognizing(self):
        self.textarea.setReadOnly(True)
        self.textarea.setPlainText("正在识别...")
        self._set_result_display("", muted=True)
        self._update_detected_lang_tag()

    def show_capturing(self):
        self.textarea.setReadOnly(True)
        self.textarea.setPlainText("正在获取选中文本...")
        self._set_result_display("", muted=True)
        self._update_detected_lang_tag()

    @staticmethod
    def empty_selection_hint() -> str:
        return EMPTY_SELECTION_HINT

    def show_translating(self):
        self._set_result_display("正在翻译...", muted=True)

    def set_source_text(self, text: str):
        self.textarea.setReadOnly(False)
        self.textarea.setPlainText(text)
        self._update_detected_lang_tag()

    def set_result_text(self, text: str, *, is_error: bool = False):
        self._set_result_display(text, is_error=is_error)

    def _set_result_display(self, text: str, *, is_error: bool = False, muted: bool = False):
        full = text or ""
        self._result_full_text = full
        if is_error or muted or not full.strip():
            self._result_copy_text = ""
        else:
            self._result_copy_text = extract_primary_translation(full)
        html = rich_result_to_html(full, is_error=is_error, muted=muted)
        self.result_content.setHtml(html)

    def run_translate(self):
        self._on_translate()

    def _swap_languages(self):
        if self.source_lang.currentText() == "自动检测":
            return
        source_items = [self.source_lang.itemText(i) for i in range(self.source_lang.count())]
        target_items = [self.target_lang.itemText(i) for i in range(self.target_lang.count())]
        source_text = self.source_lang.currentText()
        target_text = self.target_lang.currentText()
        if source_text not in target_items or target_text not in source_items:
            return
        self._auto_translate_guard = True
        try:
            self.source_lang.setCurrentText(target_text)
            self.target_lang.setCurrentText(source_text)
            self._update_detected_lang_tag()
        finally:
            self._auto_translate_guard = False
        self._maybe_auto_translate()

    def _apply_result_content_height(self):
        self.result_content.setFixedHeight(self._content_height)
        self._sync_panel_size_policy()

    def _on_split_dragged(self, delta: int):
        next_textarea = self._textarea_height + delta
        next_content = self._content_height - delta
        if next_textarea < MIN_TEXTAREA_HEIGHT or next_content < MIN_CONTENT_HEIGHT:
            return
        self._textarea_height = next_textarea
        self._content_height = next_content
        self.textarea.setFixedHeight(self._textarea_height)
        self._apply_result_content_height()
        self.layout_changed.emit()

    def _on_split_drag_finished(self):
        if self._layout_save_callback is not None:
            self._layout_save_callback("split_ratio", self.split_ratio())

    def set_layout_save_callback(self, callback):
        self._layout_save_callback = callback

    def split_ratio(self) -> float:
        total = self._textarea_height + self._content_height
        if total <= 0:
            return 0.5
        return self._textarea_height / total

    def apply_split_ratio(self, ratio: float, total: int | None = None):
        """按比例分配输入区 / 结果区高度；total 为两者之和（恢复窗口尺寸时传入）。"""
        ratio = min(1.0, max(0.0, float(ratio)))
        if total is None:
            total = self._textarea_height + self._content_height
        total = max(MIN_TEXTAREA_HEIGHT + MIN_CONTENT_HEIGHT, int(total))
        next_textarea = max(
            MIN_TEXTAREA_HEIGHT,
            min(total - MIN_CONTENT_HEIGHT, round(total * ratio)),
        )
        next_content = max(MIN_CONTENT_HEIGHT, total - next_textarea)
        self._textarea_height = next_textarea
        self._content_height = next_content
        self.textarea.setFixedHeight(self._textarea_height)
        self._apply_result_content_height()

    def set_pinned(self, pinned: bool):
        self._pinned = bool(pinned)
        if self._show_header:
            self.pin_btn.set_active(self._pinned)

    def is_pinned(self) -> bool:
        return self._pinned

    def apply_content_height(self, height: int):
        self._content_height = max(MIN_CONTENT_HEIGHT, height)
        self._apply_result_content_height()

    def content_height(self) -> int:
        return self._content_height

    def textarea_height(self) -> int:
        return self._textarea_height

    def preferred_height(self) -> int:
        tool_bar = WIDGET_MARGIN_V * 2 + 28
        lang_bar = WIDGET_MARGIN_V * 2 + 24
        split_block = SPLIT_LINE_BLOCK_HEIGHT
        header = HEADER_BAR_HEIGHT if self._show_header else 0
        fixed = (
            header
            + tool_bar
            + WIDGET_MARGIN_V
            + lang_bar
            + split_block
            + RESULT_HEADER_HEIGHT
        )
        return fixed + self._textarea_height + self._content_height

    def _toggle_pin(self):
        window = self.window()
        if not window or not hasattr(window, "set_stays_on_top"):
            return
        self._pinned = not self._pinned
        self.pin_btn.set_active(self._pinned)
        window.set_stays_on_top(self._pinned)
        if self._layout_save_callback is not None:
            self._layout_save_callback("window_pinned", self._pinned)
