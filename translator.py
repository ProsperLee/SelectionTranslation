# -*- coding: utf-8 -*-
"""国内免密钥翻译服务（translators + 有道词典公开接口）。"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable

os.environ.setdefault('translators_default_region', 'CN')

# 国内可直连、无需官方 API Key 的引擎（按推荐顺序）
CN_ENGINES = ('bing', 'youdao', 'sogou', 'alibaba', 'iciba')

ENGINE_LABELS = {
    'auto': '自动选择',
    'bing': '必应翻译',
    'youdao': '有道翻译',
    'sogou': '搜狗翻译',
    'alibaba': '阿里翻译',
    'iciba': '金山词霸',
}

# 旧配置 / 失效引擎 → 新引擎
ENGINE_ALIASES = {
    '自动选择': 'auto',
    'auto': 'auto',
    'google': 'auto',
    'Google 翻译': 'auto',
    'GoogleTranslator': 'auto',
    'myMemory': 'bing',
    'MyMemory': 'bing',
    'MyMemoryTranslator': 'bing',
    'baidu': 'youdao',
    '百度翻译': 'youdao',
    'BaiduTranslator': 'youdao',
    '必应翻译': 'bing',
    '有道翻译': 'youdao',
    '搜狗翻译': 'sogou',
    '阿里翻译': 'alibaba',
    '金山词霸': 'iciba',
    'bing': 'bing',
    'youdao': 'youdao',
    'sogou': 'sogou',
    'alibaba': 'alibaba',
    'iciba': 'iciba',
}

# 界面常用语言（应用内统一 code）
UI_LANGUAGE_ITEMS: list[tuple[str, str]] = [
    ('自动检测', 'auto'),
    ('中文', 'zh-CN'),
    ('英语', 'en'),
    ('日语', 'ja'),
    ('韩语', 'ko'),
    ('法语', 'fr'),
    ('德语', 'de'),
    ('西班牙语', 'es'),
    ('俄语', 'ru'),
    ('葡萄牙语', 'pt'),
    ('意大利语', 'it'),
    ('泰语', 'th'),
    ('越南语', 'vi'),
    ('阿拉伯语', 'ar'),
    ('印尼语', 'id'),
    ('马来语', 'ms'),
    ('土耳其语', 'tr'),
    ('波兰语', 'pl'),
    ('荷兰语', 'nl'),
    ('瑞典语', 'sv'),
    ('乌克兰语', 'uk'),
    ('印地语', 'hi'),
]

# 各引擎实际支持的常用语言（基于 translators.get_languages 实测）
_ENGINE_COMMON_CODES: dict[str, frozenset[str]] = {
    'bing': frozenset({
        'auto', 'zh-CN', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru', 'pt', 'it',
        'th', 'vi', 'ar', 'id', 'ms', 'tr', 'pl', 'nl', 'sv', 'uk', 'hi',
    }),
    'youdao': frozenset({
        'auto', 'zh-CN', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru', 'pt', 'it',
        'th', 'vi', 'ar', 'id', 'ms', 'tr', 'pl', 'nl', 'sv', 'uk', 'hi',
    }),
    'sogou': frozenset({
        'auto', 'zh-CN', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru', 'pt', 'it',
        'th', 'vi', 'ar', 'pl', 'nl', 'sv',
    }),
    'alibaba': frozenset({
        'auto', 'zh-CN', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru', 'pt', 'it',
        'th', 'vi', 'ar', 'id', 'ms', 'tr', 'pl', 'nl', 'sv', 'uk', 'hi',
    }),
    'iciba': frozenset({
        'auto', 'zh-CN', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru', 'pt', 'it',
        'th', 'vi', 'ar', 'id', 'ms', 'tr', 'pl', 'nl', 'sv', 'uk', 'hi',
    }),
}

# 应用 code → 各引擎 API code
_ENGINE_LANG_API: dict[str, dict[str, str]] = {
    'bing': {'zh-CN': 'zh-Hans', 'zh-TW': 'zh-Hant'},
    'youdao': {'zh-CN': 'zh-CHS', 'zh-TW': 'zh-CHT'},
    'sogou': {'zh-CN': 'zh-CHS', 'zh-TW': 'zh-CHS'},
    'alibaba': {'zh-CN': 'zh', 'zh-TW': 'zh-tw'},
    'iciba': {'zh-CN': 'zh', 'zh-TW': 'zh'},
}


def languages_for_engine(engine: str | None, *, allow_auto: bool = True) -> dict[str, str]:
    """返回指定引擎可用的界面语言 {显示名: code}。"""
    key = normalize_engine(engine)
    if key == 'auto':
        # 自动选择：取所有引擎交集，保证回退时语言仍可用
        supported = None
        for codes in _ENGINE_COMMON_CODES.values():
            supported = codes if supported is None else (supported & codes)
        supported = supported or frozenset({'auto', 'zh-CN', 'en'})
    else:
        supported = _ENGINE_COMMON_CODES.get(key, frozenset({'auto', 'zh-CN', 'en'}))
    result: dict[str, str] = {}
    for name, code in UI_LANGUAGE_ITEMS:
        if code == 'auto' and not allow_auto:
            continue
        if code in supported:
            result[name] = code
    if '中文' not in result and 'zh-CN' in supported:
        result['中文'] = 'zh-CN'
    if '英语' not in result and 'en' in supported:
        result['英语'] = 'en'
    return result


def coerce_language_code(code: str | None, engine: str | None,
                         *, fallback: str = 'en', allow_auto: bool = True) -> str:
    """若当前语言不被引擎支持，回退到中文/英语等可用项。"""
    langs = languages_for_engine(engine, allow_auto=allow_auto)
    codes = set(langs.values())
    if code in codes:
        return code  # type: ignore[return-value]
    if allow_auto and 'auto' in codes and code == 'auto':
        return 'auto'
    if 'zh-CN' in codes and fallback == 'zh-CN':
        return 'zh-CN'
    if 'en' in codes:
        return 'en'
    if 'zh-CN' in codes:
        return 'zh-CN'
    return next(iter(codes), 'en')


def language_label(code: str, engine: str | None = None) -> str:
    langs = languages_for_engine(engine, allow_auto=True)
    for name, value in langs.items():
        if value == code:
            return name
    for name, value in UI_LANGUAGE_ITEMS:
        if value == code:
            return name
    return code or ''


def normalize_engine(engine: str | None) -> str:
    if not engine:
        return 'auto'
    return ENGINE_ALIASES.get(engine, ENGINE_ALIASES.get(engine.strip(), 'auto'))


def engine_display_name(engine: str | None) -> str:
    key = normalize_engine(engine)
    return ENGINE_LABELS.get(key, key)


def map_lang_for_engine(code: str | None, engine: str | None) -> str:
    """把应用内语言 code 转成指定引擎的 API code。"""
    if not code or code == 'auto':
        return 'auto'
    key = normalize_engine(engine)
    if key == 'auto':
        # 自动选择时先按必应规则；真正请求时会再按具体引擎映射
        key = 'bing'
    api_map = _ENGINE_LANG_API.get(key, {})
    return api_map.get(code, code)


_translators_module = None
_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/122.0.0.0 Safari/537.36'
)


def _get_translators():
    global _translators_module
    if _translators_module is None:
        import translators as translators_module
        _translators_module = translators_module
    return _translators_module


def detect_lang_simple(text: str) -> str:
    if re.search(r'[\u4e00-\u9fff]', text or ''):
        return 'zh-CN'
    return 'en'


def split_long_text(text: str, max_len: int = 4500) -> list[str]:
    text = text or ''
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for para in text.split('\n'):
        piece = para + '\n'
        if size + len(piece) > max_len and buf:
            chunks.append(''.join(buf).rstrip('\n'))
            buf = [piece]
            size = len(piece)
        else:
            buf.append(piece)
            size += len(piece)
    if buf:
        chunks.append(''.join(buf).rstrip('\n'))
    return chunks or [text]


def _engine_chain(preferred: str) -> Iterable[str]:
    preferred = normalize_engine(preferred)
    if preferred == 'auto':
        return CN_ENGINES
    rest = [e for e in CN_ENGINES if e != preferred]
    return (preferred, *rest)


def _translate_chunk(text: str, target: str, source: str, engine: str) -> str:
    ts = _get_translators()
    return ts.translate_text(
        query_text=text,
        translator=engine,
        from_language=source,
        to_language=target,
    )


def translate_plain(text: str, target: str = 'zh-CN', source: str = 'auto',
                    engine: str = 'auto') -> tuple[str, str, str]:
    """返回 (译文, 使用的引擎, 检测到的源语言)。"""
    text = (text or '').strip()
    if not text:
        return '', '', ''

    detected = source if source != 'auto' else detect_lang_simple(text)
    if source == 'auto' and target in ('zh-CN', 'zh') and detected == 'zh-CN':
        return text, 'skip', 'zh-CN'

    chunks = split_long_text(text)
    errors: list[str] = []

    for provider in _engine_chain(engine):
        supported = _ENGINE_COMMON_CODES.get(provider, frozenset())
        src_code = 'auto' if source == 'auto' else source
        if src_code != 'auto' and src_code not in supported:
            errors.append(f'{provider}: 不支持源语言 {src_code}')
            continue
        if target not in supported and target not in ('zh', 'zh-CN'):
            # zh-CN 已在 supported 集合中；此处兜底
            errors.append(f'{provider}: 不支持目标语言 {target}')
            continue
        to_lang = map_lang_for_engine(target, provider)
        from_lang = map_lang_for_engine(source, provider)
        try:
            parts = [
                _translate_chunk(chunk, to_lang, from_lang, provider)
                for chunk in chunks
            ]
            result = '\n'.join(p for p in parts if p is not None).strip()
            if result:
                return result, provider, detected
        except Exception as exc:  # noqa: BLE001 - 多引擎回退
            errors.append(f'{provider}: {exc}')
            continue

    detail = '；'.join(errors[-3:]) if errors else '未知错误'
    raise RuntimeError(f'翻译失败（国内免费引擎均不可用）：{detail}')


def _http_get_json(url: str, timeout: float = 8.0) -> dict | None:
    req = urllib.request.Request(url, headers={'User-Agent': _UA, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError, ValueError):
        return None


def _strip_html(value: str) -> str:
    value = html.unescape(value or '')
    value = re.sub(r'<br\s*/?>', '\n', value, flags=re.I)
    value = re.sub(r'</p\s*>', '\n', value, flags=re.I)
    value = re.sub(r'<[^>]+>', '', value)
    value = re.sub(r'[ \t]+\n', '\n', value)
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


def _first_text(node) -> str:
    if node is None:
        return ''
    if isinstance(node, str):
        return _strip_html(node)
    if isinstance(node, list):
        for item in node:
            text = _first_text(item)
            if text:
                return text
        return ''
    if isinstance(node, dict):
        for key in ('i', 'tr', 'l', 'value', 'name', 'word', 'text'):
            if key in node:
                text = _first_text(node[key])
                if text:
                    return text
        for value in node.values():
            text = _first_text(value)
            if text:
                return text
    return ''


def fetch_youdao_dict(query: str) -> dict | None:
    """拉取有道词典公开 JSON（免 Key），用于丰富短词/短语结果。"""
    query = (query or '').strip()
    if not query or len(query) > 40 or '\n' in query:
        return None
    # 句子偏长时词典收益低
    if len(query.split()) > 6 and not re.search(r'[\u4e00-\u9fff]', query):
        return None
    url = 'https://dict.youdao.com/jsonapi?' + urllib.parse.urlencode({'q': query})
    return _http_get_json(url)


def _collect_phonetics(data: dict) -> str:
    word = None
    simple = data.get('simple') or {}
    words = simple.get('word') if isinstance(simple, dict) else None
    if isinstance(words, list) and words:
        word = words[0]
    if not isinstance(word, dict):
        ec = data.get('ec') or {}
        ec_words = ec.get('word') if isinstance(ec, dict) else None
        if isinstance(ec_words, list) and ec_words:
            word = ec_words[0]
    if not isinstance(word, dict):
        return ''
    uk = word.get('ukphone') or ''
    us = word.get('usphone') or ''
    parts = []
    if uk:
        parts.append(f'英 [{uk}]')
    if us:
        parts.append(f'美 [{us}]')
    return '  '.join(parts)


def _collect_explains(data: dict) -> list[str]:
    lines: list[str] = []
    ec = data.get('ec') or {}
    words = ec.get('word') if isinstance(ec, dict) else None
    if isinstance(words, list):
        for word in words:
            if not isinstance(word, dict):
                continue
            for block in word.get('trs') or []:
                text = _first_text(block)
                if text and text not in lines:
                    lines.append(text)
    return lines[:8]


def _collect_phrases(data: dict) -> list[str]:
    lines: list[str] = []
    phrs = data.get('phrs') or {}
    items = phrs.get('phrs') if isinstance(phrs, dict) else None
    if not isinstance(items, list):
        return lines
    for item in items[:6]:
        phr = (item or {}).get('phr') if isinstance(item, dict) else None
        if not isinstance(phr, dict):
            continue
        head = _first_text(phr.get('headword'))
        meaning = _first_text(phr.get('trs'))
        if head and meaning:
            lines.append(f'{head}  {meaning}')
        elif head:
            lines.append(head)
    return lines


def _collect_examples(data: dict) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    blng = data.get('blng_sents_part') or {}
    items = blng.get('sentence-pair') if isinstance(blng, dict) else None
    if not isinstance(items, list):
        return pairs
    for item in items[:4]:
        if not isinstance(item, dict):
            continue
        src = _strip_html(item.get('sentence') or item.get('sentence-eng') or '')
        dst = _strip_html(item.get('sentence-translation') or '')
        if src or dst:
            pairs.append((src, dst))
    return pairs


def _collect_web_means(data: dict) -> list[str]:
    lines: list[str] = []
    web = data.get('web_trans') or data.get('web_phrase') or {}
    if isinstance(web, dict):
        web_list = web.get('web-translation') or web.get('web_translation') or []
        if isinstance(web_list, list):
            for item in web_list[:5]:
                if not isinstance(item, dict):
                    continue
                key = _first_text(item.get('key'))
                values = item.get('trans') or item.get('value') or []
                means = []
                if isinstance(values, list):
                    for v in values[:3]:
                        means.append(_first_text(v))
                mean_text = '；'.join(m for m in means if m)
                if key and mean_text:
                    lines.append(f'{key}：{mean_text}')
                elif key:
                    lines.append(key)
    return lines


def _collect_html_snippet(data: dict) -> str:
    """尽量取出词典接口里可读的 HTML 片段（解密失败则忽略）。"""
    for key in ('oxfordAdvanceHtml', 'html_content', 'html'):
        node = data.get(key)
        if isinstance(node, str) and '<' in node:
            return _strip_html(node)[:800]
        if isinstance(node, dict):
            for sub in ('html', 'content', 'data', 'value'):
                value = node.get(sub)
                if isinstance(value, str) and '<' in value and 'encrypted' not in value.lower():
                    return _strip_html(value)[:800]
    return ''


def extract_primary_translation(text: str) -> str:
    """从丰富结果中提取可复制的核心译文（去掉音标/例句/来源等）。"""
    text = (text or "").strip()
    if not text:
        return ""
    # 分区标题或来源行之后都不是核心译文
    parts = re.split(r"\n(?=【|——)", text, maxsplit=1)
    primary = parts[0].strip()
    # 去掉误夹在首段的来源尾巴
    primary = re.split(r"\n——", primary, maxsplit=1)[0].strip()
    return primary


# 结果区字段颜色
RESULT_COLOR_PRIMARY = "#f5f5f5"
RESULT_COLOR_SECTION = "#088fff"
RESULT_COLOR_PHONETIC = "#9e9e9e"
RESULT_COLOR_BODY = "#d0d0d0"
RESULT_COLOR_EXAMPLE_SRC = "#8a8a8a"
RESULT_COLOR_EXAMPLE_DST = "#e6e6e6"
RESULT_COLOR_META = "#666666"
RESULT_COLOR_ERROR = "#ff6b6b"
RESULT_COLOR_MUTED = "#888888"


def _html_escape(text: str) -> str:
    return html.escape(text or "", quote=True).replace("\n", "<br/>")


def _span(text: str, color: str, *, bold: bool = False) -> str:
    weight = "font-weight:600;" if bold else ""
    return f'<span style="color:{color};{weight}">{_html_escape(text)}</span>'


def rich_result_to_html(text: str, *, is_error: bool = False, muted: bool = False) -> str:
    """把丰富结果转成带字段颜色的 HTML，供结果区展示。"""
    text = (text or "").strip()
    if not text:
        return ""
    if is_error:
        return _span(text, RESULT_COLOR_ERROR)
    if muted:
        return _span(text, RESULT_COLOR_MUTED)

    blocks = re.split(r"\n\n+", text)
    parts: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith("——"):
            parts.append(_span(block, RESULT_COLOR_META))
            continue

        title_match = re.match(r"^(【[^】]+】)(.*)$", block, flags=re.S)
        if title_match:
            title = title_match.group(1)
            body = (title_match.group(2) or "").lstrip("\n")
            if title == "【音标】":
                parts.append(
                    _span(title, RESULT_COLOR_SECTION, bold=True)
                    + _span(body, RESULT_COLOR_PHONETIC)
                )
                continue
            if "双语例句" in title:
                lines_html: list[str] = [_span(title, RESULT_COLOR_SECTION, bold=True)]
                for raw_line in body.split("\n"):
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    # 例句原文（带序号）与缩进译文分色
                    if re.match(r"^\d+\.\s", line):
                        lines_html.append(_span(line, RESULT_COLOR_EXAMPLE_SRC))
                    elif line.startswith("   ") or line.startswith("\t"):
                        lines_html.append(_span(line.strip(), RESULT_COLOR_EXAMPLE_DST))
                    else:
                        lines_html.append(_span(line, RESULT_COLOR_BODY))
                parts.append("<br/>".join(lines_html))
                continue

            lines_html = [_span(title, RESULT_COLOR_SECTION, bold=True)]
            if body:
                for raw_line in body.split("\n"):
                    if raw_line.strip():
                        lines_html.append(_span(raw_line, RESULT_COLOR_BODY))
            parts.append("<br/>".join(lines_html))
            continue

        # 首段核心译文
        parts.append(_span(block, RESULT_COLOR_PRIMARY, bold=True))

    return "<br/><br/>".join(parts)


def format_rich_result(plain: str, query: str, engine: str,
                       dict_data: dict | None = None) -> str:
    """把译文 + 词典信息整理成可读的丰富结果。"""
    sections: list[str] = [plain.strip() if plain else '']
    if not dict_data:
        label = engine_display_name(engine)
        if label and sections[0]:
            sections.append(f'\n—— 来源：{label}（免费/免密钥）')
        return '\n'.join(s for s in sections if s).strip()

    phonetic = _collect_phonetics(dict_data)
    explains = _collect_explains(dict_data)
    phrases = _collect_phrases(dict_data)
    examples = _collect_examples(dict_data)
    webs = _collect_web_means(dict_data)
    html_snip = _collect_html_snippet(dict_data)

    blocks: list[str] = [sections[0]]
    if phonetic:
        blocks.append(f'【音标】{phonetic}')
    if explains:
        blocks.append('【释义】\n' + '\n'.join(f'· {line}' for line in explains))
    if phrases:
        blocks.append('【短语】\n' + '\n'.join(f'· {line}' for line in phrases))
    if webs:
        blocks.append('【网络释义】\n' + '\n'.join(f'· {line}' for line in webs))
    if examples:
        lines = []
        for idx, (src, dst) in enumerate(examples, 1):
            lines.append(f'{idx}. {src}')
            if dst:
                lines.append(f'   {dst}')
        blocks.append('【双语例句】\n' + '\n'.join(lines))
    if html_snip:
        blocks.append('【扩展释义】\n' + html_snip)

    label = engine_display_name(engine)
    blocks.append(f'—— 来源：{label} + 有道词典公开数据（免费/免密钥）')
    return '\n\n'.join(b for b in blocks if b).strip()


def translate_text(text: str, target: str = 'zh-CN', source: str = 'auto',
                   engine: str = 'auto', rich: bool = True) -> tuple[str, str, str]:
    """
    翻译入口。
    返回 (结果文本, 检测到的源语言, 使用的服务名)。
    """
    plain, used_engine, detected = translate_plain(text, target=target, source=source, engine=engine)
    if not rich or used_engine == 'skip':
        return plain, detected, used_engine

    dict_data = fetch_youdao_dict(text.strip())
    rich_text = format_rich_result(plain, text, used_engine, dict_data)
    return rich_text, detected, used_engine
