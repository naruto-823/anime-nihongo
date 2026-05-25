from app.models import Episode, GrammarPoint, Series, Vocab
from app.services import conversation


def _episode(db_session):
    s = Series(title="サンプル", is_current=True)
    ep = Episode(series=s, number=1, source="upload", status="ready")
    db_session.add(s)
    db_session.commit()
    return ep


def test_conversation_turn(client, db_session, monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json",
                        lambda **kw: {"reply": "そうだね。"})
    ep = _episode(db_session)
    resp = client.post("/api/conversation/turn", json={
        "episode_id": ep.id, "character": "アキラ",
        "history": [], "user_text": "こんにちは"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "そうだね。"


def test_conversation_feedback_mines_srs(client, db_session, monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json", lambda **kw: {
        "corrections": [{"original": "x", "fixed": "y", "explain": "z"}],
        "suggestions": ["s"],
        "new_vocab": [{"headword": "感想", "reading": "かんそう",
                       "meaning_zh": "感想"}],
        "weak_grammar_keys": ["wk-gram"],
    })
    ep = _episode(db_session)
    db_session.add(GrammarPoint(key="wk-gram", name="〜wk", jlpt_level="N2",
                                explanation="x", status="seen"))
    db_session.commit()

    resp = client.post("/api/conversation/feedback", json={
        "episode_id": ep.id,
        "history": [{"role": "user", "text": "x"}]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["corrections"][0]["fixed"] == "y"
    # 新词进了 Vocab 并入 SRS；薄弱语法点入 SRS
    v = db_session.query(Vocab).filter_by(headword="感想").one()
    assert v.in_srs is True
    gp = db_session.query(GrammarPoint).filter_by(key="wk-gram").one()
    assert gp.in_srs is True and gp.status == "learning"
