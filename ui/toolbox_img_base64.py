"""工具箱 · 图片 ↔ Base64。"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.text_utils import disable_label_selection
from ui.toolbox_widgets import (
    CARD_QSS,
    EDGE_SCROLLBAR_QSS,
    ImageDropZone,
    PreviewBox,
    field_label,
    mark_check_option,
    set_status,
    status_label,
    style_edit,
)


def _guess_mime(path: str = "", data: bytes | None = None) -> str:
    lower = path.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".svg"):
        return "image/svg+xml"
    if data and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data and data[:2] == b"\xff\xd8":
        return "image/jpeg"
    return "image/png"


class ImgBase64Page(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._encode_bytes = b""
        self._encode_mime = "image/png"
        self._decode_data_url = ""
        self._decode_timer = QTimer(self)
        self._decode_timer.setSingleShot(True)
        self._decode_timer.setInterval(280)
        self._decode_timer.timeout.connect(self._run_decode)
        self._build()

    def _build(self) -> None:
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:transparent;border:none;}}{EDGE_SCROLLBAR_QSS}"
        )
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self._scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._scroll)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 14, 0)  # 内容与滚动条留距
        lay.setSpacing(12)

        # 编码卡
        enc = QFrame()
        enc.setObjectName("toolCard")
        enc.setStyleSheet(CARD_QSS)
        enc_lay = QVBoxLayout(enc)
        enc_lay.setContentsMargins(12, 12, 12, 12)
        enc_lay.setSpacing(10)
        enc_head = QHBoxLayout()
        t1 = QLabel("图片 → 编码")
        disable_label_selection(t1)
        t1.setStyleSheet("color:#e8e8e8;font-size:13px;font-weight:500;background:transparent;")
        self._enc_status = status_label()
        enc_head.addWidget(t1)
        enc_head.addWidget(self._enc_status, 1)
        enc_lay.addLayout(enc_head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.addWidget(field_label("选择图片"), 0, 0)
        grid.addWidget(field_label("Base64 编码（纯数据）"), 0, 1)
        self._drop = ImageDropZone()
        self._drop.setMinimumHeight(200)
        grid.addWidget(self._drop, 1, 0, 3, 1)
        self._out_pure = QTextEdit()
        self._out_pure.setReadOnly(True)
        self._out_pure.setPlaceholderText("iVBORw0KGgoAAAANSUhEUg...")
        style_edit(self._out_pure)
        self._out_pure.setMinimumHeight(90)
        grid.addWidget(self._out_pure, 1, 1)
        grid.addWidget(field_label("Data URL（可直接用于 img src）"), 2, 1)
        self._out_data = QTextEdit()
        self._out_data.setReadOnly(True)
        self._out_data.setPlaceholderText("data:image/...;base64,...")
        style_edit(self._out_data)
        self._out_data.setMinimumHeight(90)
        grid.addWidget(self._out_data, 3, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(1, 1)
        grid.setRowStretch(3, 1)
        enc_lay.addLayout(grid, 1)
        lay.addWidget(enc)

        # 解码卡
        dec = QFrame()
        dec.setObjectName("toolCard")
        dec.setStyleSheet(CARD_QSS)
        dec_lay = QVBoxLayout(dec)
        dec_lay.setContentsMargins(12, 12, 12, 12)
        dec_lay.setSpacing(10)
        dec_head = QHBoxLayout()
        t2 = QLabel("解码 → 图片")
        disable_label_selection(t2)
        t2.setStyleSheet("color:#e8e8e8;font-size:13px;font-weight:500;background:transparent;")
        self._dec_status = status_label()
        dec_head.addWidget(t2)
        dec_head.addWidget(self._dec_status, 1)
        dec_lay.addLayout(dec_head)

        type_row = QHBoxLayout()
        type_row.setSpacing(16)
        type_row.addWidget(field_label("输入类型"))
        pure_wrap, self._type_pure = mark_check_option("Base64 编码", True)
        data_wrap, self._type_data = mark_check_option("Data URL", False)
        type_row.addWidget(pure_wrap)
        type_row.addWidget(data_wrap)
        type_row.addStretch(1)
        dec_lay.addLayout(type_row)

        # 互斥：像单选，但样式同设置页勾选框
        self._type_pure.toggled.connect(self._on_pure_toggled)
        self._type_data.toggled.connect(self._on_data_toggled)

        io = QGridLayout()
        io.setHorizontalSpacing(12)
        io.setVerticalSpacing(8)
        self._in_label = field_label("Base64 编码（纯数据）")
        io.addWidget(self._in_label, 0, 0)
        io.addWidget(field_label("预览"), 0, 1)
        self._decode_input = QTextEdit()
        self._decode_input.setPlaceholderText("iVBORw0KGgoAAAANSUhEUg...")
        style_edit(self._decode_input)
        self._decode_input.setMinimumHeight(200)
        io.addWidget(self._decode_input, 1, 0)
        self._preview = PreviewBox("输入内容后自动预览")
        self._preview.setMinimumHeight(200)
        io.addWidget(self._preview, 1, 1)
        io.setColumnStretch(0, 1)
        io.setColumnStretch(1, 1)
        io.setRowStretch(1, 1)
        dec_lay.addLayout(io, 1)
        lay.addWidget(dec, 1)

        self._drop.clicked.connect(self._pick_file)
        self._drop.files_dropped.connect(self._on_files)
        self._drop.image_pasted.connect(self._on_bytes)
        self._decode_input.textChanged.connect(lambda: self._decode_timer.start())
        self._preview.download_clicked.connect(self._download_decode)

    def _on_pure_toggled(self, checked: bool) -> None:
        if checked:
            if self._type_data.isChecked():
                self._type_data.setChecked(False)
            self._on_type_change()
        elif not self._type_data.isChecked():
            self._type_pure.setChecked(True)

    def _on_data_toggled(self, checked: bool) -> None:
        if checked:
            if self._type_pure.isChecked():
                self._type_pure.setChecked(False)
            self._on_type_change()
        elif not self._type_pure.isChecked():
            self._type_data.setChecked(True)

    def try_paste_image(self) -> bool:
        return self._drop.try_clipboard_image()

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg);;All (*.*)",
        )
        if path:
            self._load_path(path)

    def _on_files(self, paths: list) -> None:
        if paths:
            self._load_path(paths[0])

    def _on_bytes(self, data: bytes, mime: str) -> None:
        self._apply_encode(data, mime or "image/png")

    def _load_path(self, path: str) -> None:
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            set_status(self._enc_status, f"读取失败：{exc}", False)
            return
        self._apply_encode(data, _guess_mime(path, data))

    def _apply_encode(self, data: bytes, mime: str) -> None:
        if not data:
            set_status(self._enc_status, "空文件", False)
            return
        self._encode_bytes = data
        self._encode_mime = mime
        b64 = base64.b64encode(data).decode("ascii")
        self._out_pure.setPlainText(b64)
        self._out_data.setPlainText(f"data:{mime};base64,{b64}")
        pix = QPixmap()
        pix.loadFromData(data)
        self._drop.set_preview(pix if not pix.isNull() else None)
        set_status(self._enc_status, f"已编码 · {len(data)} 字节", True)

    def _on_type_change(self) -> None:
        if self._type_pure.isChecked():
            self._in_label.setText("Base64 编码（纯数据）")
            self._decode_input.setPlaceholderText("iVBORw0KGgoAAAANSUhEUg...")
        else:
            self._in_label.setText("Data URL")
            self._decode_input.setPlaceholderText("data:image/png;base64,...")
        self._run_decode()

    def _to_data_url(self) -> str:
        raw = self._decode_input.toPlainText().strip()
        if not raw:
            return ""
        if self._type_data.isChecked() or raw.startswith("data:"):
            return raw
        # strip whitespace / newlines in pure base64
        cleaned = re.sub(r"\s+", "", raw)
        return f"data:image/png;base64,{cleaned}"

    def _run_decode(self) -> None:
        edit = self._decode_input
        vbar = edit.verticalScrollBar()
        hbar = edit.horizontalScrollBar()
        outer = self._scroll.verticalScrollBar()
        vpos, hpos, opos = vbar.value(), hbar.value(), outer.value()

        data_url = self._to_data_url()
        if not data_url:
            self._decode_data_url = ""
            self._preview.clear()
            set_status(self._dec_status, "")
            self._restore_decode_scroll(vpos, hpos, opos)
            return
        m = re.match(r"^data:([^;]+);base64,(.+)$", data_url, re.DOTALL)
        if not m:
            self._preview.clear()
            set_status(self._dec_status, "格式无效", False)
            self._restore_decode_scroll(vpos, hpos, opos)
            return
        mime, b64 = m.group(1), re.sub(r"\s+", "", m.group(2))
        try:
            data = base64.b64decode(b64, validate=False)
        except Exception:
            self._preview.clear()
            set_status(self._dec_status, "Base64 解码失败", False)
            self._restore_decode_scroll(vpos, hpos, opos)
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            self._preview.clear()
            set_status(self._dec_status, "图片无效", False)
            self._restore_decode_scroll(vpos, hpos, opos)
            return
        self._decode_data_url = f"data:{mime};base64,{b64}"
        self._preview.set_pixmap(pix)
        set_status(self._dec_status, "预览就绪", True)
        self._restore_decode_scroll(vpos, hpos, opos)

    def _restore_decode_scroll(self, vpos: int, hpos: int, opos: int) -> None:
        """解码失败/成功后保持输入区与页面滚动位置，避免跳回开头。"""
        edit = self._decode_input
        vbar = edit.verticalScrollBar()
        hbar = edit.horizontalScrollBar()
        outer = self._scroll.verticalScrollBar()

        def _apply() -> None:
            vbar.setValue(vpos)
            hbar.setValue(hpos)
            outer.setValue(opos)

        _apply()
        QTimer.singleShot(0, _apply)

    def _download_decode(self) -> None:
        if not self._decode_data_url:
            return
        m = re.match(r"^data:([^;]+);base64,(.+)$", self._decode_data_url)
        if not m:
            return
        mime, b64 = m.group(1), m.group(2)
        ext = (mime.split("/")[-1] or "png").replace("jpeg", "jpg")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", f"image.{ext}", f"Image (*.{ext});;All (*.*)"
        )
        if not path:
            return
        try:
            Path(path).write_bytes(base64.b64decode(b64))
            set_status(self._dec_status, "已保存", True)
        except OSError as exc:
            set_status(self._dec_status, f"保存失败：{exc}", False)
