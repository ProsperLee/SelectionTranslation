"""工具箱 · 二维码生成。"""

from __future__ import annotations

import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.icons import PrimaryButton
from ui.paths import choose_save_file
from ui.text_utils import disable_label_selection
from ui.toolbox_widgets import (
    PreviewBox,
    field_label,
    set_status,
    status_label,
    style_edit,
)
from ui.styles import COMBO_POPUP_VIEW_QSS

_EC_MAP = {
    "L": "7%",
    "M": "15%",
    "Q": "25%",
    "H": "30%",
}

_PREVIEW_SIZE = 180
_FIELD_H = 36  # 下拉 / 自定义尺寸输入统一高度


def _form_combo_qss() -> str:
    # 不复用 COMBO_QSS 的 min-height/padding，避免高度被样式表顶开
    return f"""
QComboBox {{
    background: #292929;
    color: #f2f2f2;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0 {10}px;
    min-height: {_FIELD_H}px;
    max-height: {_FIELD_H}px;
    font-size: 14px;
}}
QComboBox:hover {{
    border-color: #454545;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
""" + COMBO_POPUP_VIEW_QSS


def _form_line_qss() -> str:
    return f"""
QLineEdit {{
    background: #292929;
    color: #f2f2f2;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 0 8px;
    min-height: {_FIELD_H}px;
    max-height: {_FIELD_H}px;
    font-size: 14px;
    selection-background-color: #088fff;
    selection-color: #ffffff;
}}
QLineEdit:focus {{
    border-color: #088fff;
}}
"""


def _ec_const(level: str):
    import qrcode

    return {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }.get(level, qrcode.constants.ERROR_CORRECT_M)


class _QrTextEdit(QPlainTextEdit):
    """回车生成；Shift+回车换行。"""

    generate_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.generate_requested.emit()
            return
        super().keyPressEvent(event)


class QrcodePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix: QPixmap | None = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 14, 0)
        root.setSpacing(16)

        # —— 上半：左输入 | 右结果（预览 → 摘要 → 生成）——
        top = QHBoxLayout()
        top.setSpacing(20)
        top.setAlignment(Qt.AlignmentFlag.AlignTop)

        left = QVBoxLayout()
        left.setSpacing(8)
        self._text = _QrTextEdit()
        self._text.setPlaceholderText("请输入文字（回车生成，Shift+回车换行）")
        style_edit(self._text)
        # 与右侧「预览+摘要+按钮」总高度大致对齐
        right_stack_h = _PREVIEW_SIZE + 8 + 22 + 8 + 32
        self._text.setFixedHeight(right_stack_h)
        left.addWidget(self._text)
        self._status = status_label()
        self._status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left.addWidget(self._status)
        top.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._preview = PreviewBox("点击生成后显示二维码", fixed_size=_PREVIEW_SIZE)
        right.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignHCenter)
        self._summary = QLabel("QR Code, 15%容错, 300x300px")
        disable_label_selection(self._summary)
        self._summary.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self._summary.setFixedWidth(_PREVIEW_SIZE)
        self._summary.setFixedHeight(22)
        self._summary.setStyleSheet(
            "color:#888;font-size:12px;background:transparent;padding:0;margin:0;"
        )
        right.addWidget(self._summary, 0, Qt.AlignmentFlag.AlignHCenter)
        self._gen_btn = PrimaryButton("生成二维码")
        self._gen_btn.setFixedWidth(_PREVIEW_SIZE)
        self._gen_btn.clicked.connect(self._generate)
        right.addWidget(self._gen_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        top.addLayout(right, 0)
        root.addLayout(top)

        # —— 下半：两列参数，标签与控件垂直居中；控件同高 ——
        self._level = QComboBox()
        for code, label in _EC_MAP.items():
            self._level.addItem(label, code)
        self._level.setCurrentIndex(1)
        self._level.setStyleSheet(_form_combo_qss())

        self._size = QComboBox()
        for n in (300, 400, 500, 600):
            self._size.addItem(f"{n}x{n}px", n)
        self._size.addItem("自定义尺寸", "custom")
        self._size.setStyleSheet(_form_combo_qss())

        self._custom = QLineEdit()
        self._custom.setPlaceholderText("800")
        self._custom.setText("800")
        self._custom.setStyleSheet(_form_line_qss())
        self._custom.setFixedWidth(88)
        self._custom_unit = QLabel("px")
        self._custom_unit.setStyleSheet("color:#888;font-size:13px;background:transparent;")
        self._custom.hide()
        self._custom_unit.hide()

        size_row = QWidget()
        size_row.setStyleSheet("background:transparent;")
        sr = QHBoxLayout(size_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(8)
        sr.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        sr.addWidget(self._size, 1)
        sr.addWidget(self._custom, 0, Qt.AlignmentFlag.AlignVCenter)
        sr.addWidget(self._custom_unit, 0, Qt.AlignmentFlag.AlignVCenter)

        self._version = QComboBox()
        for v in range(1, 41):
            m = 17 + 4 * v
            self._version.addItem(f"{v} ({m}*{m})", v)
        self._version.setStyleSheet(_form_combo_qss())

        self._margin = QComboBox()
        for n in range(1, 5):
            self._margin.addItem(f"{n}个色块", n)
        self._margin.setStyleSheet(_form_combo_qss())

        for w in (self._level, self._size, self._version, self._margin, self._custom):
            w.setFixedHeight(_FIELD_H)

        form = QGridLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)
        form.setColumnMinimumWidth(0, 48)
        form.setColumnMinimumWidth(2, 48)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        def _cell(row: int, col: int, lab: str, widget: QWidget) -> None:
            fl = field_label(lab)
            fl.setFixedWidth(48)
            form.addWidget(
                fl,
                row,
                col,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            form.addWidget(widget, row, col + 1)

        _cell(0, 0, "容错率", self._level)
        _cell(0, 2, "尺寸", size_row)
        _cell(1, 0, "码版本", self._version)
        _cell(1, 2, "码边距", self._margin)

        root.addLayout(form)
        root.addStretch(1)

        self._text.generate_requested.connect(self._generate)
        self._preview.download_clicked.connect(self._download)
        self._preview.copy_clicked.connect(self._copy_image)
        self._size.currentIndexChanged.connect(self._on_size_change)
        self._level.currentIndexChanged.connect(self._on_option_change)
        self._version.currentIndexChanged.connect(self._on_option_change)
        self._margin.currentIndexChanged.connect(self._on_option_change)
        self._custom.editingFinished.connect(self._on_option_change)
        self._update_summary()

    def _pixel_size(self) -> int:
        data = self._size.currentData()
        if data == "custom":
            try:
                n = int(self._custom.text().strip())
            except ValueError:
                n = 300
            return max(64, min(2048, n))
        return int(data or 300)

    def _on_size_change(self) -> None:
        custom = self._size.currentData() == "custom"
        self._custom.setVisible(custom)
        self._custom_unit.setVisible(custom)
        self._on_option_change()

    def _on_option_change(self) -> None:
        self._update_summary()
        if self._text.toPlainText().strip():
            self._generate()

    def _update_summary(self) -> None:
        size = self._pixel_size()
        pct = self._level.currentText()
        self._summary.setText(f"QR Code, {pct}容错, {size}x{size}px")

    def _generate(self) -> None:
        text = self._text.toPlainText()
        if not text.strip():
            set_status(self._status, "请输入内容", False)
            return
        try:
            import qrcode
            from PIL import Image
        except ImportError:
            set_status(self._status, "缺少 qrcode / Pillow 依赖", False)
            return

        size = self._pixel_size()
        version = int(self._version.currentData() or 1)
        border = int(self._margin.currentData() or 1)
        ec = _ec_const(str(self._level.currentData() or "M"))
        try:
            qr = qrcode.QRCode(
                version=version,
                error_correction=ec,
                box_size=10,
                border=border,
            )
            qr.add_data(text)
            # 以所选版本为下限，容量不足时自动升版，避免 Code length overflow
            qr.make(fit=True)
            used_version = int(qr.version or version)
            if used_version != version:
                self._version.blockSignals(True)
                idx = self._version.findData(used_version)
                if idx >= 0:
                    self._version.setCurrentIndex(idx)
                self._version.blockSignals(False)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img = img.resize((size, size), Image.Resampling.NEAREST)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(buf.getvalue(), "PNG")
        except Exception as exc:
            self._preview.clear()
            self._pix = None
            set_status(self._status, f"生成失败：{exc}", False)
            return

        self._pix = pix
        self._preview.set_pixmap(pix)
        self._update_summary()
        if used_version > version:
            set_status(self._status, f"已生成（已自动升至版本 {used_version}）", True)
        else:
            set_status(self._status, "已生成", True)

    def _download(self) -> None:
        if self._pix is None or self._pix.isNull():
            return
        path = choose_save_file(self, "保存二维码", "PNG (*.png);;All (*.*)", "qrcode.png")
        if not path:
            return
        if self._pix.save(path, "PNG"):
            set_status(self._status, "已保存", True)
        else:
            set_status(self._status, "保存失败", False)

    def _copy_image(self) -> None:
        if self._pix is None or self._pix.isNull():
            set_status(self._status, "暂无图片可复制", False)
            return
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setPixmap(self._pix)
        set_status(self._status, "已复制图片", True)
