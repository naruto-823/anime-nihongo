from functools import lru_cache

from sudachipy import Dictionary, SplitMode

# 用于挑候选词的实义词性
_CONTENT_POS = {"名詞", "動詞", "形容詞", "副詞"}
# 太基础、不值得进复习的词
_STOP_FORMS = {"する", "ある", "いる", "なる", "これ", "それ", "あれ", "こと", "もの"}


@lru_cache(maxsize=1)
def _tokenizer():
    return Dictionary().create()


def _kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _has_kanji(s: str) -> bool:
    return any("一" <= c <= "鿿" for c in s)


def _canonical_reading(form: str) -> str:
    """对辞书形重新分词，取与辞书形匹配的规范读音（平假名）。"""
    kata = "".join(m.reading_form() for m in _tokenizer().tokenize(form, SplitMode.A))
    return _kata_to_hira(kata)


def to_furigana(text: str) -> list[dict]:
    """把文本切成段：含汉字的段为 {"t": 表层, "r": 平假名读音}，纯假名为 {"t": 表层}。"""
    segs: list[dict] = []
    for m in _tokenizer().tokenize(text, SplitMode.C):
        surface = m.surface()
        if _has_kanji(surface):
            segs.append({"t": surface, "r": _kata_to_hira(m.reading_form())})
        else:
            segs.append({"t": surface})
    return segs


def extract_vocab_candidates(text: str) -> list[dict]:
    """抽取实义词候选：辞书形、读音、词性。同一辞书形去重。"""
    seen: dict[str, dict] = {}
    for m in _tokenizer().tokenize(text, SplitMode.C):
        pos = m.part_of_speech()[0]
        if pos not in _CONTENT_POS:
            continue
        form = m.dictionary_form()
        if form in _STOP_FORMS:
            continue
        if form not in seen:
            seen[form] = {
                "headword": form,
                "reading": _canonical_reading(form),
                "pos": pos,
            }
    return list(seen.values())
