from app.grammar_loader import load_grammar_seed
from app.models import Episode, GrammarPoint, Line, Series, Vocab
from app.services import pipeline


def _episode_with_lines(db_session, texts):
    series = Series(title="番")
    ep = Episode(series=series, number=1, source="upload", status="processing",
                 total_lines=len(texts))
    for i, t in enumerate(texts):
        ep.lines.append(Line(idx=i, text_jp=t, processed=False))
    ep.scenes_split = True
    db_session.add(series)
    db_session.commit()
    return ep


def _fake_llm(system, user, model=None, max_tokens=4000):
    # 按 user 里给出的行 idx 回填注释；测试不关心真实语义
    import json
    payload = json.loads(user)
    return {
        "lines": [
            {"idx": ln["idx"], "translation_zh": "译:" + ln["text"],
             "grammar_notes": [{"point": "〜にあたって", "explain": "示例"}],
             "register_tag": "casual",
             "grammar_point_keys": ["ni-atatte"]}
            for ln in payload["lines"]
        ],
        "vocab": [{"headword": "猫", "reading": "ねこ", "meaning_zh": "猫",
                   "pos": "名詞", "jlpt_level": "N5"}],
    }


def test_process_episode_annotates_lines(db_session, monkeypatch):
    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)
    ep = _episode_with_lines(db_session, ["猫が走る", "今日はいい天気だ"])

    pipeline.process_episode(db_session, ep.id, batch_size=10)

    db_session.refresh(ep)
    assert ep.status == "ready"
    assert ep.processed_lines == 2
    lines = db_session.query(Line).filter_by(episode_id=ep.id).all()
    assert all(ln.processed for ln in lines)
    assert all(ln.translation_zh and ln.furigana for ln in lines)
    assert all(ln.grammar_point_keys == ["ni-atatte"] for ln in lines)


def test_process_episode_creates_vocab_and_flips_grammar(db_session, monkeypatch):
    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)
    ep = _episode_with_lines(db_session, ["猫が走る"])

    pipeline.process_episode(db_session, ep.id, batch_size=10)

    assert db_session.query(Vocab).filter_by(headword="猫").count() == 1
    gp = db_session.query(GrammarPoint).filter_by(key="ni-atatte").one()
    assert gp.status == "seen"
    assert gp.source_line_id is not None


def test_process_episode_is_resumable(db_session, monkeypatch):
    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)
    ep = _episode_with_lines(db_session, ["猫が走る", "犬が寝る"])
    # 预先把第 0 行标记为已加工
    ep.lines[0].processed = True
    ep.processed_lines = 1
    db_session.commit()

    calls = []
    orig = _fake_llm

    def counting_llm(system, user, model=None, max_tokens=4000):
        import json
        calls.append(len(json.loads(user)["lines"]))
        return orig(system, user, model, max_tokens)

    monkeypatch.setattr(pipeline.llm, "call_json", counting_llm)
    pipeline.process_episode(db_session, ep.id, batch_size=10)
    # 只应处理剩下的 1 行
    assert calls == [1]
    assert ep.status == "ready"


def test_process_episode_sets_failed_on_llm_error(db_session, monkeypatch):
    import pytest

    from app.services.llm import LLMError

    load_grammar_seed(db_session)

    def failing_llm(**kwargs):
        raise LLMError("boom")

    monkeypatch.setattr(pipeline.llm, "call_json", failing_llm)
    ep = _episode_with_lines(db_session, ["猫が走る"])

    with pytest.raises(LLMError):
        pipeline.process_episode(db_session, ep.id)

    db_session.refresh(ep)
    assert ep.status == "failed"
    lines = db_session.query(Line).filter_by(episode_id=ep.id).all()
    assert all(not ln.processed for ln in lines)
