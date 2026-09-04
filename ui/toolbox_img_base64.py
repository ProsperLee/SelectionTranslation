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
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.icons import IconButton
from ui.text_utils import disable_label_selection
from ui.toolbox_widgets import (
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
    # 上传框 / 解码输入 / 预览 统一尺寸，保证上下网格对齐
    _IO_H = 168

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

        # 整页共用一张网格：两列等宽，上传框与解码输入同列同高
        page = QVBoxLayout(inner)
        page.setContentsMargins(0, 0, 14, 0)
        page.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # —— 编码区标题 ——
        enc_head = QWidget()
        eh = QHBoxLayout(enc_head)
        eh.setContentsMargins(0, 0, 0, 0)
        eh.setSpacing(8)
        t1 = QLabel("图片 → 编码")
        disable_label_selection(t1)
        t1.setStyleSheet(
            "color:#e8e8e8;font-size:13px;font-weight:500;background:transparent;"
        )
        self._enc_status = status_label()
        eh.addWidget(t1)
        eh.addWidget(self._enc_status, 1)
        grid.addWidget(enc_head, 0, 0, 1, 2)

        grid.addWidget(field_label("选择图片"), 1, 0)
        pure_lab_row = QWidget()
        pure_lab_row.setStyleSheet("background:transparent;")
        plr = QHBoxLayout(pure_lab_row)
        plr.setContentsMargins(0, 0, 0, 0)
        plr.setSpacing(4)
        plr.addWidget(field_label("Base64 编码（纯数据）"), 1)
        self._copy_pure = IconButton("copy.svg", size=13, variant="light", button_size=22)
        self._copy_pure.setToolTip("复制")
        self._copy_pure.clicked.connect(lambda: self._copy_text(self._out_pure, "已复制 Base64"))
        plr.addWidget(self._copy_pure, 0, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(pure_lab_row, 1, 1)

        self._drop = ImageDropZone()
        self._size_io(self._drop)

        enc_right = QWidget()
        enc_right.setStyleSheet("background:transparent;")
        self._size_io(enc_right)
        er = QVBoxLayout(enc_right)
        er.setContentsMargins(0, 0, 0, 0)
        er.setSpacing(8)
        self._out_pure = QTextEdit()
        self._out_pure.setReadOnly(True)
        self._out_pure.setPlaceholderText("iVBORw0KGgoAAAANSUhEUg...")
        style_edit(self._out_pure)
        er.addWidget(self._out_pure, 1)

        data_lab_row = QWidget()
        data_lab_row.setStyleSheet("background:transparent;")
        dlr = QHBoxLayout(data_lab_row)
        dlr.setContentsMargins(0, 0, 0, 0)
        dlr.setSpacing(4)
        dlr.addWidget(field_label("Data URL（可直接用于 img src）"), 1)
        self._copy_data = IconButton("copy.svg", size=13, variant="light", button_size=22)
        self._copy_data.setToolTip("复制")
        self._copy_data.clicked.connect(lambda: self._copy_text(self._out_data, "已复制 Data URL"))
        dlr.addWidget(self._copy_data, 0, Qt.AlignmentFlag.AlignVCenter)
        er.addWidget(data_lab_row)

        self._out_data = QTextEdit()
        self._out_data.setReadOnly(True)
        self._out_data.setPlaceholderText("data:image/...;base64,...")
        style_edit(self._out_data)
        er.addWidget(self._out_data, 1)

        grid.addWidget(self._drop, 2, 0)
        grid.addWidget(enc_right, 2, 1)

        # —— 解码区标题 + 类型 ——
        dec_head = QWidget()
        dh = QHBoxLayout(dec_head)
        dh.setContentsMargins(0, 8, 0, 0)
        dh.setSpacing(8)
        t2 = QLabel("解码 → 图片")
        disable_label_selection(t2)
        t2.setStyleSheet(
            "color:#e8e8e8;font-size:13px;font-weight:500;background:transparent;"
        )
        self._dec_status = status_label()
        dh.addWidget(t2)
        dh.addWidget(self._dec_status, 1)
        grid.addWidget(dec_head, 3, 0, 1, 2)

        type_row = QWidget()
        type_row.setStyleSheet("background:transparent;")
        tr = QHBoxLayout(type_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(16)
        tr.addWidget(field_label("输入类型"))
        pure_wrap, self._type_pure = mark_check_option("Base64 编码", True)
        data_wrap, self._type_data = mark_check_option("Data URL", False)
        tr.addWidget(pure_wrap)
        tr.addWidget(data_wrap)
        tr.addStretch(1)
        grid.addWidget(type_row, 4, 0, 1, 2)

        self._type_pure.toggled.connect(self._on_pure_toggled)
        self._type_data.toggled.connect(self._on_data_toggled)

        self._in_label = field_label("Base64 编码（纯数据）")
        grid.addWidget(self._in_label, 5, 0)
        grid.addWidget(field_label("预览"), 5, 1)

        self._decode_input = QTextEdit()
        self._decode_input.setPlaceholderText("iVBORw0KGgoAAAANSUhEUg...")
        style_edit(self._decode_input)
        self._size_io(self._decode_input)

        self._preview = PreviewBox("输入内容后自动预览")
        self._size_io(self._preview)

        grid.addWidget(self._decode_input, 6, 0)
        grid.addWidget(self._preview, 6, 1)

        page.addLayout(grid)
        page.addStretch(1)

        self._drop.clicked.connect(self._pick_file)
        self._drop.files_dropped.connect(self._on_files)
        self._drop.image_pasted.connect(self._on_bytes)
        self._decode_input.textChanged.connect(lambda: self._decode_timer.start())
        self._preview.download_clicked.connect(self._download_decode)
        self._preview.copy_clicked.connect(self._copy_decode_image)

    def _size_io(self, widget: QWidget) -> None:
        """主网格单元格：固定同高，横向随列拉伸同宽。"""
        h = self._IO_H
        widget.setFixedHeight(h)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _copy_text(self, edit: QTextEdit, ok_msg: str) -> None:
        text = edit.toPlainText().strip()
        if not text:
            set_status(self._enc_status, "暂无内容可复制", False)
            return
        QGuiApplication.clipboard().setText(text)
        set_status(self._enc_status, ok_msg, True)

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

    def _copy_decode_image(self) -> None:
        pix = self._preview.pixmap()
        if pix is None or pix.isNull():
            set_status(self._dec_status, "暂无图片可复制", False)
            return
        QGuiApplication.clipboard().setPixmap(pix)
        set_status(self._dec_status, "已复制图片", True)
