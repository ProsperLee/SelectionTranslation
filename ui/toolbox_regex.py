"""工具箱 · 正则表达式。"""

from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.icons import load_icon
from ui.text_utils import disable_label_selection
from ui.toolbox_widgets import (
    EDGE_SCROLLBAR_QSS,
    field_label,
    mark_check_option,
    style_edit,
)


class RegexPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._run()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent;border:none;}}{EDGE_SCROLLBAR_QSS}"
        )
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 14, 0)
        root.setSpacing(14)

        head = QHBoxLayout()
        head.addWidget(field_label("正则表达式"))
        head.addStretch(1)
        self._btn_copy = QPushButton(" 复制")
        self._btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_copy.setIcon(load_icon("copy.svg", 13, "#9a9a9a"))
        self._btn_copy.setStyleSheet(
            """
            QPushButton {
                background: transparent; border: none; border-radius: 4px;
                color: #9a9a9a; font-size: 13px; padding: 4px 8px;
            }
            QPushButton:hover { background: #2a2a2a; color: #e0e0e0; }
            """
        )
        self._btn_copy.clicked.connect(self._copy_regex)
        head.addWidget(self._btn_copy)
        root.addLayout(head)

        pat_row = QHBoxLayout()
        slash_l = QLabel("/")
        slash_l.setStyleSheet(
            "color:#888;font-family:Consolas;font-size:18px;background:transparent;"
        )
        self._pattern = QLineEdit()
        self._pattern.setPlaceholderText("输入正则表达式...")
        style_edit(self._pattern)
        self._flags_suffix = QLabel("/ g")
        self._flags_suffix.setStyleSheet(
            "color:#088fff;font-family:Consolas;font-size:15px;background:transparent;"
        )
        pat_row.addWidget(slash_l)
        pat_row.addWidget(self._pattern, 1)
        pat_row.addWidget(self._flags_suffix)
        root.addLayout(pat_row)

        flags_row = QHBoxLayout()
        flags_row.setSpacing(18)
        g_wrap, self._flag_g = mark_check_option("g 全局匹配", True)
        i_wrap, self._flag_i = mark_check_option("i 忽略大小写")
        m_wrap, self._flag_m = mark_check_option("m 多行模式")
        s_wrap, self._flag_s = mark_check_option("s 点号匹配换行")
        for wrap, box in (
            (g_wrap, self._flag_g),
            (i_wrap, self._flag_i),
            (m_wrap, self._flag_m),
            (s_wrap, self._flag_s),
        ):
            box.toggled.connect(lambda _=False: self._run())
            flags_row.addWidget(wrap)
        flags_row.addStretch(1)
        root.addLayout(flags_row)

        root.addWidget(field_label("测试字符串"))
        self._text = QPlainTextEdit()
        self._text.setPlaceholderText("输入或粘贴要测试的文本")
        style_edit(self._text)
        self._text.setFixedHeight(80)
        root.addWidget(self._text)

        res_head = QHBoxLayout()
        res_head.addWidget(field_label("匹配结果"))
        res_head.addStretch(1)
        self._count = QLabel("0个匹配")
        disable_label_selection(self._count)
        self._set_count(0)
        res_head.addWidget(self._count)
        root.addLayout(res_head)

        self._highlight = QLabel("暂无匹配结果")
        self._highlight.setWordWrap(True)
        self._highlight.setTextFormat(Qt.TextFormat.RichText)
        self._highlight.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._highlight.setFixedHeight(80)
        self._apply_highlight_style(empty=True)
        root.addWidget(self._highlight)

        root.addWidget(field_label("匹配详情"))
        self._detail_empty = QLabel("暂无匹配详情")
        self._detail_empty.setStyleSheet("color:#666;font-size:12px;background:transparent;")
        root.addWidget(self._detail_empty)

        self._detail_host = QWidget()
        self._detail_lay = QVBoxLayout(self._detail_host)
        self._detail_lay.setContentsMargins(0, 0, 0, 0)
        self._detail_lay.setSpacing(4)
        root.addWidget(self._detail_host)
        root.addStretch(1)

        self._pattern.textChanged.connect(self._run)
        self._text.textChanged.connect(self._run)

    def _apply_highlight_style(self, *, empty: bool) -> None:
        color = "#666" if empty else "#f2f2f2"
        self._highlight.setStyleSheet(
            f"""
            QLabel {{
                background:#292929; border:1px solid #333333; border-radius:6px;
                color:{color}; font-size:13px;
                font-family: Consolas, "Courier New", monospace;
                padding:12px 14px;
            }}
            """
        )

    def _flags(self) -> str:
        flags = ""
        if self._flag_g.isChecked():
            flags += "g"
        if self._flag_i.isChecked():
            flags += "i"
        if self._flag_m.isChecked():
            flags += "m"
        if self._flag_s.isChecked():
            flags += "s"
        return flags

    def _py_flags(self) -> int:
        f = 0
        if self._flag_i.isChecked():
            f |= re.IGNORECASE
        if self._flag_m.isChecked():
            f |= re.MULTILINE
        if self._flag_s.isChecked():
            f |= re.DOTALL
        return f

    def _update_suffix(self) -> None:
        flags = self._flags()
        self._flags_suffix.setText(f"/ {flags}" if flags else "/")

    def _clear_details(self) -> None:
        while self._detail_lay.count():
            item = self._detail_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _run(self) -> None:
        self._update_suffix()
        pattern = self._pattern.text()
        text = self._text.toPlainText()
        self._clear_details()

        if not pattern:
            self._set_count(0)
            self._highlight.setText("暂无匹配结果")
            self._apply_highlight_style(empty=True)
            self._detail_empty.show()
            return

        try:
            cre = re.compile(pattern, self._py_flags())
        except re.error as exc:
            self._set_count(0)
            self._highlight.setText(f"正则无效：{html.escape(str(exc))}")
            self._apply_highlight_style(empty=True)
            self._detail_empty.show()
            return

        matches: list[re.Match] = []
        if self._flag_g.isChecked():
            for m in cre.finditer(text):
                matches.append(m)
                if len(matches) >= 10000:
                    break
        else:
            m = cre.search(text)
            if m:
                matches.append(m)

        self._set_count(len(matches))
        if not matches:
            self._highlight.setText(html.escape(text) if text else "暂无匹配结果")
            self._apply_highlight_style(empty=not bool(text))
            self._detail_empty.show()
            return

        parts: list[str] = []
        last = 0
        for m in matches:
            if m.start() < last:
                continue
            parts.append(html.escape(text[last : m.start()]))
            parts.append(
                f'<span style="color:#088fff;font-weight:600;">【{html.escape(m.group(0))}】</span>'
            )
            last = m.end()
        parts.append(html.escape(text[last:]))
        self._highlight.setText("".join(parts) or "暂无匹配结果")
        self._apply_highlight_style(empty=False)

        self._detail_empty.hide()
        for i, m in enumerate(matches):
            row = QFrame()
            row.setStyleSheet(
                "QFrame{background:#1a1a1a;border:1px solid #333333;border-radius:6px;}"
            )
            hl = QHBoxLayout(row)
            hl.setContentsMargins(10, 4, 10, 4)
            hl.setSpacing(8)
            idx = QLabel(f"#{i + 1}")
            idx.setStyleSheet(
                "color:#888;font-size:12px;font-family:Consolas;background:transparent;"
            )
            idx.setFixedWidth(32)
            val = QLabel(f'"{html.escape(m.group(0))}"')
            val.setTextFormat(Qt.TextFormat.RichText)
            val.setStyleSheet(
                "color:#088fff;font-size:12px;font-family:Consolas;background:transparent;"
            )
            val.setWordWrap(True)
            pos = QLabel(f"位置: {m.start()}")
            pos.setStyleSheet("color:#888;font-size:11px;background:transparent;")
            hl.addWidget(idx)
            hl.addWidget(val, 1)
            hl.addWidget(pos)
            self._detail_lay.addWidget(row)

    def _set_count(self, n: int) -> None:
        self._count.setText(f"{n}个匹配")
        if n > 0:
            self._count.setStyleSheet(
                """
                QLabel {
                    color:#5cb3ff; font-size:12px;
                    background: rgba(8,143,255,0.12);
                    border:1px solid rgba(8,143,255,0.35);
                    border-radius:999px; padding:3px 10px;
                }
                """
            )
        else:
            self._count.setStyleSheet(
                """
                QLabel {
                    color:#888; font-size:12px; background:#1a1a1a;
                    border:1px solid #333333; border-radius:999px; padding:3px 10px;
                }
                """
            )

    def _copy_regex(self) -> None:
        literal = f"/{self._pattern.text()}/{self._flags()}"
        QGuiApplication.clipboard().setText(literal)
        self._btn_copy.setText(" 已复制")
        QTimer.singleShot(1200, lambda: self._btn_copy.setText(" 复制"))
