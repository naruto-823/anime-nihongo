from app.models import GrammarPoint, Vocab


def _seed(db):
    for i in range(12):
        db.add(Vocab(headword=f"語{i}", reading=f"よ{i}", meaning_zh=f"義{i}",
                     pos="名", jlpt_level="N5"))
    for i in range(4):
        db.add(GrammarPoint(key=f"N5-g{i}", name=f"〜文法{i}", jlpt_level="N5",
                            explanation=f"含義{i}", curated=True))
    db.commit()


def test_get_tower_map(client, db_session):
    _seed(db_session)
    body = client.get("/api/tower").json()
    assert body["levels"][0]["level"] == "N5"
    assert body["levels"][0]["unlocked"] is True


def test_get_quiz(client, db_session):
    _seed(db_session)
    body = client.get("/api/tower/quiz?level=N5&zone=0&stage=0").json()
    assert len(body["questions"]) >= 1
    q = body["questions"][0]
    assert q["answer"] in q["options"]
    assert q["item"]["kind"] in {"vocab", "grammar"}


def test_get_player(client, db_session):
    body = client.get("/api/player").json()
    assert body["total_xp"] == 0 and body["player_level"] == 1


def test_submit_quiz_updates_and_returns(client, db_session):
    _seed(db_session)
    vid = db_session.query(Vocab).first().id
    body = {
        "level": "N5", "zone": 0, "stage": 0, "boss": False,
        "results": [{"item": {"kind": "vocab", "id": vid}, "correct": True}],
    }
    out = client.post("/api/tower/submit", json=body).json()
    assert out["stars"] == 3 and out["passed"] is True
    assert out["xp_gained"] == 10
    # 地图应解锁下一关
    m = client.get("/api/tower").json()
    assert m["levels"][0]["zones"][0]["stages"][1]["unlocked"] is True
