"""工具箱 · 二维码生成。"""

from __future__ import annotations

import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.text_utils import disable_label_selection
from ui.toolbox_widgets import (
    COMBO_QSS,
    PreviewBox,
    field_label,
    set_status,
    status_label,
    style_edit,
)

_EC_MAP = {
    "L": "7%",
    "M": "15%",
    "Q": "25%",
    "H": "30%",
}

_PREVIEW_SIZE = 220


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
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 14, 0)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 左：输入（与右侧预览顶对齐）
        left = QVBoxLayout()
        left.setSpacing(8)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._text = _QrTextEdit()
        self._text.setPlaceholderText("请输入文字（回车生成，Shift+回车换行）")
        style_edit(self._text)
        self._text.setMinimumHeight(_PREVIEW_SIZE)
        left.addWidget(self._text, 1)
        self._status = status_label()
        self._status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left.addWidget(self._status)
        root.addLayout(left, 1)

        # 右：固定预览 + 选项（顶对齐，避免摘要区被纵向撑开）
        right = QVBoxLayout()
        right.setSpacing(10)
        right.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._preview = PreviewBox("点击生成后显示二维码", fixed_size=_PREVIEW_SIZE)
        right.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignHCenter)

        self._summary = QLabel("QR Code, 15%容错, 300x300px")
        disable_label_selection(self._summary)
        self._summary.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self._summary.setFixedWidth(_PREVIEW_SIZE)
        self._summary.setFixedHeight(22)
        self._summary.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._summary.setStyleSheet(
            "color:#888;font-size:12px;background:transparent;padding:0;margin:0;"
        )
        right.addWidget(self._summary, 0, Qt.AlignmentFlag.AlignHCenter)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.setColumnMinimumWidth(0, 52)
        form.setColumnStretch(1, 1)

        self._level = QComboBox()
        for code, label in _EC_MAP.items():
            self._level.addItem(label, code)
        self._level.setCurrentIndex(1)
        self._level.setStyleSheet(COMBO_QSS)

        self._size = QComboBox()
        for n in (300, 400, 500, 600):
            self._size.addItem(f"{n}x{n}px", n)
        self._size.addItem("自定义尺寸", "custom")
        self._size.setStyleSheet(COMBO_QSS)

        self._custom = QLineEdit()
        self._custom.setPlaceholderText("800")
        self._custom.setText("800")
        style_edit(self._custom)
        self._custom_unit = QLabel("px")
        self._custom_unit.setStyleSheet("color:#888;font-size:13px;background:transparent;")
        self._custom_wrap = QWidget()
        self._custom_wrap.setStyleSheet("background:transparent;")
        cw = QHBoxLayout(self._custom_wrap)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(8)
        cw.addWidget(self._custom, 1)
        cw.addWidget(self._custom_unit, 0)
        self._custom_wrap.hide()

        self._version = QComboBox()
        for v in range(1, 41):
            m = 17 + 4 * v
            self._version.addItem(f"{v} ({m}*{m})", v)
        self._version.setStyleSheet(COMBO_QSS)

        self._margin = QComboBox()
        for n in range(1, 5):
            self._margin.addItem(f"{n}个色块", n)
        self._margin.setStyleSheet(COMBO_QSS)

        def _add_row(row: int, lab: str, widget: QWidget) -> None:
            form.addWidget(
                field_label(lab),
                row,
                0,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            form.addWidget(widget, row, 1)

        _add_row(0, "容错率", self._level)
        _add_row(1, "尺寸", self._size)
        # 自定义尺寸单独下一行，与上方下拉同列宽对齐
        form.addWidget(self._custom_wrap, 2, 1)
        _add_row(3, "码版本", self._version)
        _add_row(4, "码边距", self._margin)

        form_wrap = QWidget()
        form_wrap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        form_wrap.setFixedWidth(_PREVIEW_SIZE)
        form_wrap.setLayout(form)
        right.addWidget(form_wrap, 0, Qt.AlignmentFlag.AlignHCenter)
        right.addStretch(1)
        root.addLayout(right, 0)

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
        self._custom_wrap.setVisible(self._size.currentData() == "custom")
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
            qr.make(fit=False)
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
        set_status(self._status, "已生成", True)

    def _download(self) -> None:
        if self._pix is None or self._pix.isNull():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存二维码", "qrcode.png", "PNG (*.png);;All (*.*)"
        )
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
