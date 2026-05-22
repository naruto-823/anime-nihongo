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
    by_word = {c["headword"]: c for c in cands}
    assert "猫" in by_word
    assert "走る" in by_word          # 辞书形
    assert by_word["猫"]["reading"] == "ねこ"
    assert by_word["走る"]["reading"] == "はしる"   # 读音与辞书形匹配，而非表层形
    assert all("reading" in c and "pos" in c for c in cands)
