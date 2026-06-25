"""词性归一化:把多套乱码 pos 标注映射成结构化分类标签 + 筛选键。

数据里 pos 标注来自不同来源、风格混杂(他動1 / 名・自他動3 / イ形 / 形容動詞 /
な形容词 / 副①・自動3① 文章語 …),还混入 circled 音调与「文章語」等备注。
此处统一清洗并归类,供前端词性筛选与标签展示。
"""

import re

# circled 数字(音调标记)
_ACCENT = "⓪①②③④⑤⑥⑦⑧⑨"
_NOTE_RE = re.compile(r"文章\s*語|補動|接尾|接頭")

# 筛选键 → 中文标签
_TAG_LABEL = {
    "noun": "名词",
    "verb": "动词",
    "verb_t": "他动词",
    "verb_i": "自动词",
    "i-adj": "イ形容词",
    "na-adj": "ナ形容词",
    "adverb": "副词",
    "other": "其他",
}
# 标签展示顺序
_ORDER = ["noun", "verb", "verb_t", "verb_i", "i-adj", "na-adj", "adverb", "other"]


def _clean(raw: str) -> str:
    s = raw or ""
    for ch in _ACCENT:
        s = s.replace(ch, "")
    s = _NOTE_RE.sub("", s)
    return s


def normalize_pos(raw: str) -> dict:
    """返回 {"tags": [中文标签...], "filters": [筛选键...]}。一词多类时多键命中。"""
    s = _clean(raw)
    filters: set[str] = set()

    if "名" in s:
        filters.add("noun")

    if "動" in s and "形" not in s:  # 排除「形容動詞」误命中
        filters.add("verb")
        if "自他動" in s:
            filters.update({"verb_t", "verb_i"})
        elif "他動" in s:
            filters.add("verb_t")
        elif "自動" in s:
            filters.add("verb_i")

    # 形容词:先判 ナ形(「な形容詞」含「形容詞」子串,优先),「形動トタル」文语不计
    is_na = any(t in s for t in ("ナ形", "な形", "形容動詞", "形容动词"))
    is_i = any(t in s for t in ("イ形", "い形", "形容詞", "形容词"))
    if "トタル" not in s:
        if is_na:
            filters.add("na-adj")
        elif is_i:
            filters.add("i-adj")

    if "副" in s:
        filters.add("adverb")

    if not filters:
        filters.add("other")

    ordered = [k for k in _ORDER if k in filters]
    return {"tags": [_TAG_LABEL[k] for k in ordered], "filters": ordered}
