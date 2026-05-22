from app.services.tokenizer import extract_vocab_candidates, to_furigana


def test_furigana_attaches_reading_to_kanji():
    segs = to_furigana("今日は学校に行く")
    # 含汉字的段带读音 r；纯假名段不带
    kanji_segs = [s for s in segs if "r" in s]
    assert any(s["t"] == "今日" for s in kanji_segs)
    joined = "".join(s["t"] for s in segs)
    assert joined == "今日は学校に行く"
    for s in kanji_segs:
        assert all("぀" <= c <= "ゟ" for c in s["r"])  # 读音为平假名


def test_furigana_pure_kana_has_no_reading():
    segs = to_furigana("おはよう")
    assert all("r" not in s for s in segs)


def test_extract_vocab_candidates_returns_dictionary_forms():
    cands = extract_vocab_candidates("猫が走った")
    forms = {c["headword"] for c in cands}
    assert "猫" in forms
    assert "走る" in forms          # 辞书形
    assert all("reading" in c and "pos" in c for c in cands)
