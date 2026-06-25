from app.services.jpos import normalize_pos


def test_noun():
    r = normalize_pos("名")
    assert r["tags"] == ["名词"]
    assert set(r["filters"]) == {"noun"}


def test_transitive_godan():
    r = normalize_pos("他動1")
    assert "动词" in r["tags"] and "他动词" in r["tags"]
    assert "verb" in r["filters"] and "verb_t" in r["filters"]
    assert "verb_i" not in r["filters"]


def test_intransitive():
    r = normalize_pos("自動2")
    assert "自动词" in r["tags"]
    assert set(r["filters"]) >= {"verb", "verb_i"}
    assert "verb_t" not in r["filters"]


def test_transitive_and_intransitive():
    r = normalize_pos("名・自他動3")
    assert set(r["filters"]) >= {"noun", "verb", "verb_t", "verb_i"}


def test_i_adjective():
    r = normalize_pos("イ形")
    assert r["tags"] == ["イ形容词"]
    assert r["filters"] == ["i-adj"]


def test_na_adjective_variants():
    for raw in ("ナ形", "形容動詞", "名詞・な形容词"):
        r = normalize_pos(raw)
        assert "na-adj" in r["filters"], raw
    # 「な形容词」含「形容詞」子串,不应同时判成 i-adj
    assert "i-adj" not in normalize_pos("名词/な形容词")["filters"]


def test_adverb():
    assert normalize_pos("副")["filters"] == ["adverb"]


def test_strips_accent_and_notes():
    # circled 音调与「文章語」备注须剔除,不影响归类
    r = normalize_pos("自動3①　文章語")
    assert "verb" in r["filters"]


def test_unknown_is_other():
    r = normalize_pos("接続詞")
    assert r["filters"] == ["other"]
    assert r["tags"] == ["其他"]


def test_empty():
    r = normalize_pos("")
    assert r["filters"] == ["other"]
