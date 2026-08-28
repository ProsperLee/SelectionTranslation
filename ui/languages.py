"""界面语言与翻译引擎联动（常用语言排在前面）。"""

from __future__ import annotations

import re

from translator import (
    UI_LANGUAGE_ITEMS,
    coerce_language_code,
    language_label,
    languages_for_engine,
)

_LABEL_TO_CODE = {name: code for name, code in UI_LANGUAGE_ITEMS}


def display_to_code(label: str, engine: str, *, allow_auto: bool = True, fallback: str = "en") -> str:
    langs = languages_for_engine(engine, allow_auto=allow_auto)
    if label in langs:
        return langs[label]
    if label in _LABEL_TO_CODE:
        code = _LABEL_TO_CODE[label]
        return coerce_language_code(code, engine, fallback=fallback, allow_auto=allow_auto)
    return coerce_language_code(label, engine, fallback=fallback, allow_auto=allow_auto)


def sync_language_combos(
    source_combo,
    target_combo,
    engine: str,
    *,
    source_label: str | None = None,
    target_label: str | None = None,
):
    """按引擎刷新语言下拉，并纠正当前选项。"""
    src_map = languages_for_engine(engine, allow_auto=True)
    tgt_map = languages_for_engine(engine, allow_auto=False)

    if source_label is None:
        source_label = source_combo.currentText()
    if target_label is None:
        target_label = target_combo.currentText()

    source_code = display_to_code(source_label, engine, allow_auto=True, fallback="zh-CN")
    target_code = display_to_code(target_label, engine, allow_auto=False, fallback="en")
    source_code = coerce_language_code(source_code, engine, fallback="zh-CN", allow_auto=True)
    target_code = coerce_language_code(target_code, engine, fallback="en", allow_auto=False)

    selected_source = language_label(source_code, engine)
    selected_target = language_label(target_code, engine)

    _fill_combo(source_combo, list(src_map.keys()), selected_source)
    _fill_combo(target_combo, list(tgt_map.keys()), selected_target)
    return source_code, target_code


def _fill_combo(combo, items: list[str], selected: str):
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(items)
    index = combo.findText(selected)
    if index >= 0:
        combo.setCurrentIndex(index)
    elif items:
        combo.setCurrentIndex(0)
    combo.blockSignals(False)


def detect_language_label(text: str) -> str:
    """根据输入文本猜测语言显示名；无法判断时返回 \"--\"。"""
    text = (text or "").strip()
    if not text:
        return "检测中..."
    if re.search(r"[\u4e00-\u9fff]", text):
        return language_label("zh-CN") or "中文"
    if re.search(r"[\u3040-\u30ff\u31f0-\u31ff]", text):
        return language_label("ja") or "日语"
    if re.search(r"[\uac00-\ud7af]", text):
        return language_label("ko") or "韩语"
    if re.search(r"[\u0400-\u04ff]", text):
        return language_label("ru") or "俄语"
    if re.search(r"[a-zA-Z]", text):
        return language_label("en") or "英语"
    if re.search(r"[\u0600-\u06ff]", text):
        return language_label("ar") or "阿拉伯语"
    if re.search(r"[\u0e00-\u0e7f]", text):
        return language_label("th") or "泰语"
    if re.search(r"[\u0370-\u03ff]", text):
        return language_label("el") or "希腊语"
    return "检测中..."
