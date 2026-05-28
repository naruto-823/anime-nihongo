from app.models import Episode, GrammarPoint, Line, Series, Vocab


def _ready_episode(db_session):
    s = Series(title="番", is_current=True)
    ep = Episode(series=s, number=1, source="upload", status="ready",
                 total_lines=1, reading_done=False)
    ln = Line(episode=ep, idx=0, text_jp="猫が好き", processed=True,
              grammar_point_keys=["mai"])
    db_session.add(s)
    db_session.commit()
    return ep, ln


def test_add_vocab_to_srs(client, db_session):
    ep, ln = _ready_episode(db_session)
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", source_line_id=ln.id)
    db_session.add(v)
    db_session.commit()
    resp = client.post(f"/api/study/vocab/{v.id}/add-srs")
    assert resp.status_code == 200
    db_session.refresh(v)
    assert v.in_srs is True and v.due_date is not None


def test_add_grammar_to_srs(client, db_session):
    gp = GrammarPoint(key="mai", name="〜まい", jlpt_level="N2",
                      explanation="x", status="seen")
    db_session.add(gp)
    db_session.commit()
    resp = client.post(f"/api/study/grammar/{gp.id}/add-srs")
    assert resp.status_code == 200
    db_session.refresh(gp)
    assert gp.in_srs is True and gp.status == "learning"


def test_reading_progress_and_complete(client, db_session):
    ep, _ = _ready_episode(db_session)
    client.post(f"/api/study/episodes/{ep.id}/reading-progress",
                json={"position": 1})
    db_session.refresh(ep)
    assert ep.read_position == 1

    resp = client.post("/api/study/complete-today",
                       json={"episode_id": ep.id, "vocab_reviewed": 3})
    assert resp.status_code == 200
    assert resp.json()["streak"] >= 1
