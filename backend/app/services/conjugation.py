"""日语动词/形容词活用引擎。

输入词条(写法/读音/词性),输出完整活用表;不变形(名词/副词等)返回 None。
在读音(かな)上做活用保证正确,再回贴汉字表层。

动词类型靠 pos 编码(中文教材体系)判定:動1=五段、動2=一段、動3=サ变/カ变。
"""

import re

# 五段各结尾假名 → (あ段, い段, え段, お段)
_GODAN_ROWS = {
    "う": ("わ", "い", "え", "お"),
    "く": ("か", "き", "け", "こ"),
    "ぐ": ("が", "ぎ", "げ", "ご"),
    "す": ("さ", "し", "せ", "そ"),
    "つ": ("た", "ち", "て", "と"),
    "ぬ": ("な", "に", "ね", "の"),
    "ぶ": ("ば", "び", "べ", "ぼ"),
    "む": ("ま", "み", "め", "も"),
    "る": ("ら", "り", "れ", "ろ"),
}
# 五段 て/た 音便
_GODAN_TE = {
    "う": ("って", "った"), "つ": ("って", "った"), "る": ("って", "った"),
    "く": ("いて", "いた"), "ぐ": ("いで", "いだ"),
    "ぬ": ("んで", "んだ"), "ぶ": ("んで", "んだ"), "む": ("んで", "んだ"),
    "す": ("して", "した"),
}

# 动词活用形顺序与中文标签
_VERB_LABELS = [
    ("dictionary", "辞书形"),
    ("masu", "ます形"),
    ("te", "て形"),
    ("ta", "た形(过去)"),
    ("nai", "ない形(否定)"),
    ("nakatta", "なかった形(过去否定)"),
    ("potential", "可能形"),
    ("volitional", "意志形"),
    ("passive", "受身形"),
    ("causative", "使役形"),
    ("causative_passive", "使役受身形"),
    ("imperative", "命令形"),
    ("prohibitive", "禁止形"),
    ("conditional_ba", "条件形(ば)"),
    ("conditional_tara", "条件形(たら)"),
]


_ICHIDAN_SUFFIXES = {
    "dictionary": "る",
    "masu": "ます",
    "te": "て",
    "ta": "た",
    "nai": "ない",
    "nakatta": "なかった",
    "potential": "られる",
    "volitional": "よう",
    "passive": "られる",
    "causative": "させる",
    "causative_passive": "させられる",
    "imperative": "ろ",
    "prohibitive": "るな",
    "conditional_ba": "れば",
    "conditional_tara": "たら",
}


# サ变(する / 名词+する):作为词干后缀,词干为"" 即 する 本身
_SURU_SUFFIXES = {
    "dictionary": "する",
    "masu": "します",
    "te": "して",
    "ta": "した",
    "nai": "しない",
    "nakatta": "しなかった",
    "potential": "できる",
    "volitional": "しよう",
    "passive": "される",
    "causative": "させる",
    "causative_passive": "させられる",
    "imperative": "しろ",
    "prohibitive": "するな",
    "conditional_ba": "すれば",
    "conditional_tara": "したら",
}

# カ变 来る(かな为准,読音随活用变化)
_KURU_KANA = {
    "dictionary": "くる",
    "masu": "きます",
    "te": "きて",
    "ta": "きた",
    "nai": "こない",
    "nakatta": "こなかった",
    "potential": "こられる",
    "volitional": "こよう",
    "passive": "こられる",
    "causative": "こさせる",
    "causative_passive": "こさせられる",
    "imperative": "こい",
    "prohibitive": "くるな",
    "conditional_ba": "くれば",
    "conditional_tara": "きたら",
}


def _godan_suffixes(last: str) -> dict[str, str]:
    a, i, e, o = _GODAN_ROWS[last]
    te, ta = _GODAN_TE[last]
    return {
        "dictionary": last,
        "masu": i + "ます",
        "te": te,
        "ta": ta,
        "nai": a + "ない",
        "nakatta": a + "なかった",
        "potential": e + "る",
        "volitional": o + "う",
        "passive": a + "れる",
        "causative": a + "せる",
        "causative_passive": a + "される",
        "imperative": e,
        "prohibitive": last + "な",
        "conditional_ba": e + "ば",
        "conditional_tara": ta + "ら",
    }


_IADJ_LABELS = [
    ("present", "现在形"),
    ("past", "过去形"),
    ("negative", "否定形"),
    ("past_negative", "过去否定"),
    ("te", "て形"),
    ("adverbial", "副词形(く)"),
    ("conditional_ba", "条件形(ば)"),
]
_IADJ_SUFFIXES = {
    "present": "い", "past": "かった", "negative": "くない",
    "past_negative": "くなかった", "te": "くて", "adverbial": "く",
    "conditional_ba": "ければ",
}

_NAADJ_LABELS = [
    ("present", "现在形"),
    ("past", "过去形"),
    ("negative", "否定形"),
    ("past_negative", "过去否定"),
    ("te", "て形"),
    ("adnominal", "连体形(な)"),
    ("conditional_ba", "条件形(なら)"),
]
_NAADJ_SUFFIXES = {
    "present": "だ", "past": "だった", "negative": "じゃない",
    "past_negative": "じゃなかった", "te": "で", "adnominal": "な",
    "conditional_ba": "なら",
}


def _build(suffixes: dict[str, str], kana_stem: str, surface_stem: str,
           group: str, labels: list = _VERB_LABELS, vtype: str = "verb") -> dict:
    forms = []
    for key, label in labels:
        suf = suffixes[key]
        forms.append({
            "key": key, "label": label,
            "kana": kana_stem + suf,
            "surface": surface_stem + suf,
        })
    return {"type": vtype, "group": group, "forms": forms}


def _conjugate_i_adj(headword: str, reading: str) -> dict:
    # いい:不规则,除现在形外词干变 よ
    if reading == "いい":
        surf_stem = headword[:-1] if headword != reading else "よ"
        forms = []
        for key, label in _IADJ_LABELS:
            if key == "present":
                forms.append({"key": key, "label": label,
                              "kana": "いい", "surface": headword})
            else:
                suf = _IADJ_SUFFIXES[key]
                forms.append({"key": key, "label": label,
                              "kana": "よ" + suf, "surface": surf_stem + suf})
        return {"type": "i-adj", "group": "イ形容词", "forms": forms}

    return _build(_IADJ_SUFFIXES, reading[:-1], headword[:-1], "イ形容词",
                  _IADJ_LABELS, "i-adj")


def _conjugate_irregular(headword: str, reading: str) -> dict | None:
    """サ变(する/名词+する)与 カ变(来る)。"""
    if reading == "くる" or headword.endswith("来る"):
        kanji = headword[0] if headword != reading else None
        forms = []
        for key, label in _VERB_LABELS:
            kana = _KURU_KANA[key]
            surface = (kanji + kana[1:]) if kanji else kana
            forms.append({"key": key, "label": label, "kana": kana, "surface": surface})
        return {"type": "verb", "group": "カ变", "forms": forms}

    # サ变:词干 = 去掉结尾「する」(名词形态则词干即整词)
    kana_stem = reading[:-2] if reading.endswith("する") else reading
    surf_stem = headword[:-2] if headword.endswith("する") else headword
    return _build(_SURU_SUFFIXES, kana_stem, surf_stem, "サ变")


def _verb_group(pos: str) -> str | None:
    """从 pos 编码取动词类别:1=五段 2=一段 3=不规则。"""
    m = re.search(r"動([123])", pos)
    if not m:
        return None
    return {"1": "五段", "2": "一段", "3": "不规则"}[m.group(1)]


def conjugate(headword: str, reading: str, pos: str) -> dict | None:
    if not reading:
        return None

    # 1) 有明确动词类别数字(動1/2/3)→ 动词
    group = _verb_group(pos)
    if group == "不规则":
        return _conjugate_irregular(headword, reading)
    if group == "一段":
        return _build(_ICHIDAN_SUFFIXES, reading[:-1], headword[:-1], "一段")
    if group == "五段":
        if reading[-1] not in _GODAN_ROWS:
            return None
        return _conjugate_godan(headword, reading)

    # 2) 形容词。先判 ナ形(「な形容詞」含「形容詞」子串,须优先),再判 イ形。
    #    覆盖多套标注:イ形/ナ形、い形/な形、形容詞/形容词、形容動詞/形容动词。
    is_na = any(t in pos for t in ("ナ形", "な形", "形容動詞", "形容动词"))
    is_i = any(t in pos for t in ("イ形", "い形", "形容詞", "形容词"))
    if is_na and "トタル" not in pos:
        return _build(_NAADJ_SUFFIXES, reading, headword, "ナ形容词",
                      _NAADJ_LABELS, "na-adj")
    if is_i and "トタル" not in pos:
        return _conjugate_i_adj(headword, reading)

    # 3) 无类别数字的「動」(裸「動詞」或「名詞・動詞」)→ 用 sudachi 判真实类型;
    #    若 sudachi 判不出动词(纯名词)则视作サ变名词(名詞+する)。
    if "動" in pos and "形" not in pos:
        from app.services.tokenizer import verb_conjugation_group
        g = verb_conjugation_group(headword) or verb_conjugation_group(reading)
        if g == "一段":
            return _build(_ICHIDAN_SUFFIXES, reading[:-1], headword[:-1], "一段")
        if g == "五段" and reading[-1] in _GODAN_ROWS:
            return _conjugate_godan(headword, reading)
        return _conjugate_irregular(headword, reading)

    return None


_HONORIFIC_GODAN = {"おっしゃる", "くださる", "なさる", "いらっしゃる", "ござる"}
_ARU = {"ある", "在る", "有る"}


def _conjugate_godan(headword: str, reading: str) -> dict:
    last = reading[-1]
    suffixes = _godan_suffixes(last)

    # 行く 及其复合:て/た形音便例外(いて→って)
    if last == "く" and reading.endswith("いく"):
        suffixes["te"] = "って"
        suffixes["ta"] = "った"
        suffixes["conditional_tara"] = "ったら"

    # 敬语五段:ます形/命令形例外(おっしゃります→おっしゃいます)
    if reading in _HONORIFIC_GODAN:
        suffixes["masu"] = "います"
        suffixes["imperative"] = "い"

    result = _build(suffixes, reading[:-1], headword[:-1], "五段")

    # ある:否定为 ない(非 あらない),需整词替换
    if reading == "ある" and headword in _ARU:
        for f in result["forms"]:
            if f["key"] == "nai":
                f["kana"] = f["surface"] = "ない"
            elif f["key"] == "nakatta":
                f["kana"] = f["surface"] = "なかった"

    return result
