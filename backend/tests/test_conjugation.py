from app.services.conjugation import conjugate


def _forms(headword, reading, pos):
    """返回 {form_key: kana} 便于断言。"""
    result = conjugate(headword, reading, pos)
    assert result is not None
    return {f["key"]: f["kana"] for f in result["forms"]}, result


def test_godan_nomu_core_forms():
    forms, res = _forms("飲む", "のむ", "他動1")
    assert res["type"] == "verb"
    assert res["group"] == "五段"
    assert forms["dictionary"] == "のむ"
    assert forms["masu"] == "のみます"
    assert forms["te"] == "のんで"
    assert forms["ta"] == "のんだ"
    assert forms["nai"] == "のまない"
    assert forms["nakatta"] == "のまなかった"
    assert forms["potential"] == "のめる"
    assert forms["volitional"] == "のもう"
    assert forms["passive"] == "のまれる"
    assert forms["causative"] == "のませる"
    assert forms["imperative"] == "のめ"
    assert forms["prohibitive"] == "のむな"
    assert forms["conditional_ba"] == "のめば"
    assert forms["conditional_tara"] == "のんだら"


def test_godan_surface_uses_kanji_stem():
    result = conjugate("飲む", "のむ", "他動1")
    surf = {f["key"]: f["surface"] for f in result["forms"]}
    assert surf["masu"] == "飲みます"
    assert surf["te"] == "飲んで"
    assert surf["nai"] == "飲まない"


def test_ichidan_taberu():
    forms, res = _forms("食べる", "たべる", "他動2")
    assert res["group"] == "一段"
    assert forms["dictionary"] == "たべる"
    assert forms["masu"] == "たべます"
    assert forms["te"] == "たべて"
    assert forms["ta"] == "たべた"
    assert forms["nai"] == "たべない"
    assert forms["potential"] == "たべられる"
    assert forms["passive"] == "たべられる"
    assert forms["causative"] == "たべさせる"
    assert forms["causative_passive"] == "たべさせられる"
    assert forms["volitional"] == "たべよう"
    assert forms["imperative"] == "たべろ"
    assert forms["prohibitive"] == "たべるな"
    assert forms["conditional_ba"] == "たべれば"
    assert forms["conditional_tara"] == "たべたら"


def test_suru():
    forms, res = _forms("する", "する", "自他動3")
    assert res["group"] == "サ变"
    assert forms["masu"] == "します"
    assert forms["te"] == "して"
    assert forms["ta"] == "した"
    assert forms["nai"] == "しない"
    assert forms["potential"] == "できる"
    assert forms["passive"] == "される"
    assert forms["causative"] == "させる"
    assert forms["volitional"] == "しよう"
    assert forms["imperative"] == "しろ"
    assert forms["conditional_ba"] == "すれば"
    assert forms["conditional_tara"] == "したら"


def test_suru_noun_benkyou():
    forms, res = _forms("勉強", "べんきょう", "名・自他動3")
    assert res["group"] == "サ变"
    assert forms["dictionary"] == "べんきょうする"
    assert forms["masu"] == "べんきょうします"
    assert forms["te"] == "べんきょうして"
    assert forms["nai"] == "べんきょうしない"
    surf = {f["key"]: f["surface"] for f in res["forms"]}
    assert surf["masu"] == "勉強します"


def test_kuru():
    forms, res = _forms("来る", "くる", "自動3")
    assert res["group"] == "カ变"
    assert forms["dictionary"] == "くる"
    assert forms["masu"] == "きます"
    assert forms["te"] == "きて"
    assert forms["ta"] == "きた"
    assert forms["nai"] == "こない"
    assert forms["nakatta"] == "こなかった"
    assert forms["potential"] == "こられる"
    assert forms["volitional"] == "こよう"
    assert forms["imperative"] == "こい"
    assert forms["conditional_ba"] == "くれば"
    assert forms["conditional_tara"] == "きたら"
    surf = {f["key"]: f["surface"] for f in res["forms"]}
    assert surf["nai"] == "来ない"
    assert surf["masu"] == "来ます"


def test_iku_te_ta_exception():
    forms, _ = _forms("行く", "いく", "自動1")
    # 行く 是五段カ行,但て/た形音便例外
    assert forms["te"] == "いって"
    assert forms["ta"] == "いった"
    assert forms["conditional_tara"] == "いったら"
    assert forms["masu"] == "いきます"  # 其余规则不变


def test_aru_negative_exception():
    forms, _ = _forms("ある", "ある", "自動1")
    assert forms["nai"] == "ない"
    assert forms["nakatta"] == "なかった"
    assert forms["te"] == "あって"  # 其余规则不变
    assert forms["masu"] == "あります"


def test_honorific_godan_ossharu():
    forms, _ = _forms("おっしゃる", "おっしゃる", "他動1")
    assert forms["masu"] == "おっしゃいます"  # 非 おっしゃります
    assert forms["imperative"] == "おっしゃい"
    assert forms["te"] == "おっしゃって"


def test_i_adjective_takai():
    forms, res = _forms("高い", "たかい", "イ形")
    assert res["type"] == "i-adj"
    assert forms["present"] == "たかい"
    assert forms["past"] == "たかかった"
    assert forms["negative"] == "たかくない"
    assert forms["past_negative"] == "たかくなかった"
    assert forms["te"] == "たかくて"
    assert forms["adverbial"] == "たかく"
    assert forms["conditional_ba"] == "たかければ"
    surf = {f["key"]: f["surface"] for f in res["forms"]}
    assert surf["past"] == "高かった"


def test_ii_adjective_irregular():
    forms, _ = _forms("いい", "いい", "イ形")
    assert forms["present"] == "いい"
    assert forms["past"] == "よかった"
    assert forms["negative"] == "よくない"
    assert forms["te"] == "よくて"
    assert forms["adverbial"] == "よく"


def test_na_adjective_shizuka():
    forms, res = _forms("静か", "しずか", "ナ形")
    assert res["type"] == "na-adj"
    assert forms["present"] == "しずかだ"
    assert forms["past"] == "しずかだった"
    assert forms["negative"] == "しずかじゃない"
    assert forms["past_negative"] == "しずかじゃなかった"
    assert forms["te"] == "しずかで"
    assert forms["adnominal"] == "しずかな"
    assert forms["conditional_ba"] == "しずかなら"


def test_noun_returns_none():
    assert conjugate("天気", "てんき", "名") is None
    assert conjugate("ゆっくり", "ゆっくり", "副") is None


def test_keiyoudoushi_label_is_na_adj():
    # 项目原有手工词用「形容動詞」标注(含「動」字,勿误判为动词)
    forms, res = _forms("素敵", "すてき", "形容動詞")
    assert res["type"] == "na-adj"
    assert forms["present"] == "すてきだ"
    assert forms["adnominal"] == "すてきな"


def test_noun_verb_label_is_suru_noun():
    # 「名詞・動詞」无类别数字 → 视作サ变名词
    forms, res = _forms("優先", "ゆうせん", "名詞・動詞")
    assert res["group"] == "サ变"
    assert forms["dictionary"] == "ゆうせんする"
    assert forms["masu"] == "ゆうせんします"


def test_plain_doushi_label_uses_sudachi():
    # 裸「動詞」标注(无数字)的真实动词,靠 sudachi 判类型
    forms, res = _forms("知る", "しる", "動詞")  # 五段ラ行
    assert res["group"] == "五段"
    assert forms["te"] == "しって"
    assert forms["nai"] == "しらない"
    assert forms["masu"] == "しります"

    forms2, res2 = _forms("信じる", "しんじる", "動詞")  # 一段
    assert res2["group"] == "一段"
    assert forms2["te"] == "しんじて"


def test_archaic_keidou_taru_returns_none():
    assert conjugate("整然", "せいぜん", "形動トタル") is None


def test_alternate_adjective_labels():
    # 原有手工词的多种形容词标注变体
    assert conjugate("強い", "つよい", "形容詞")["type"] == "i-adj"
    assert conjugate("明るい", "あかるい", "い形容词")["type"] == "i-adj"
    assert conjugate("楽しい", "たのしい", "形容詞")["type"] == "i-adj"
    # な形容词/名词 含「形容詞」子串,须先判 na-adj 不被误判 i-adj
    assert conjugate("元気", "げんき", "な形容词/名词")["type"] == "na-adj"
    assert conjugate("孤独", "こどく", "名词/な形容词")["type"] == "na-adj"
    assert conjugate("不安", "ふあん", "名詞・な形容詞")["type"] == "na-adj"
