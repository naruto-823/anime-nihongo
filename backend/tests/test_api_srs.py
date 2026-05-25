from datetime import date

from app.models import Vocab


def test_due_lists_only_due_in_srs_items(client, db_session):
    today = date.today()
    db_session.add_all([
        Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=today),
        Vocab(headword="犬", reading="いぬ", meaning_zh="狗", in_srs=False),
    ])
    db_session.commit()
    body = client.get("/api/srs/due").json()
    heads = [v["headword"] for v in body["vocab"]]
    assert heads == ["猫"]


def test_review_vocab_advances_state(client, db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=date.today())
    db_session.add(v)
    db_session.commit()
    resp = client.post("/api/srs/review",
                       json={"item_type": "vocab", "item_id": v.id,
                             "grade": "good"})
    assert resp.status_code == 200
    db_session.refresh(v)
    assert v.interval_days == 1 and v.reps == 1


def test_review_rejects_bad_grade(client, db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=date.today())
    db_session.add(v)
    db_session.commit()
    resp = client.post("/api/srs/review",
                       json={"item_type": "vocab", "item_id": v.id,
                             "grade": "perfect"})
    assert resp.status_code == 422
