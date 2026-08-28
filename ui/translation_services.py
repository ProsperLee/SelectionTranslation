"""翻译服务显示名与 API code 映射（界面下拉用）。"""

from __future__ import annotations

ENGINE_ITEMS = [
    "自动选择",
    "必应翻译",
    "有道翻译",
    "搜狗翻译",
    "阿里翻译",
    "金山词霸",
]

ENGINE_ALIASES = {
    "自动选择": "自动选择",
    "自动检测": "自动选择",
    "auto": "自动选择",
    "google": "自动选择",
    "Google 翻译": "自动选择",
    "GoogleTranslator": "自动选择",
    "myMemory": "必应翻译",
    "MyMemory": "必应翻译",
    "MyMemoryTranslator": "必应翻译",
    "baidu": "有道翻译",
    "百度翻译": "有道翻译",
    "BaiduTranslator": "有道翻译",
    "bing": "必应翻译",
    "youdao": "有道翻译",
    "sogou": "搜狗翻译",
    "alibaba": "阿里翻译",
    "iciba": "金山词霸",
    "必应翻译": "必应翻译",
    "有道翻译": "有道翻译",
    "搜狗翻译": "搜狗翻译",
    "阿里翻译": "阿里翻译",
    "金山词霸": "金山词霸",
    "金山翻译": "金山词霸",
    "腾讯翻译": "自动选择",
    "谷歌翻译": "自动选择",
    "DeepL": "自动选择",
    "微软翻译": "必应翻译",
    "彩云小译": "自动选择",
}

ENGINE_DISPLAY_TO_API = {
    "自动选择": "auto",
    "必应翻译": "bing",
    "有道翻译": "youdao",
    "搜狗翻译": "sogou",
    "阿里翻译": "alibaba",
    "金山词霸": "iciba",
}


def normalize_engine(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ENGINE_ITEMS[0]
    return ENGINE_ALIASES.get(text, text if text in ENGINE_ITEMS else ENGINE_ITEMS[0])


def engine_api_code(display_name: str) -> str:
    return ENGINE_DISPLAY_TO_API.get(normalize_engine(display_name), "auto")
