from datetime import date

from app.models import UserVocabProgress, Vocab


def test_due_lists_only_due_in_srs_items(client, db_session):
    today = date.today()
    cat = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    dog = Vocab(headword="犬", reading="いぬ", meaning_zh="狗")
    db_session.add_all([cat, dog])
    db_session.flush()
    db_session.add_all([
        UserVocabProgress(user_id=1, vocab_id=cat.id, in_srs=True, due_date=today),
        UserVocabProgress(user_id=1, vocab_id=dog.id, in_srs=False),
    ])
    db_session.commit()
    body = client.get("/api/srs/due").json()
    heads = [v["headword"] for v in body["vocab"]]
    assert heads == ["猫"]


def test_review_vocab_advances_state(client, db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    db_session.add(v)
    db_session.flush()
    progress = UserVocabProgress(user_id=1, vocab_id=v.id, due_date=date.today())
    db_session.add(progress)
    db_session.commit()
    resp = client.post("/api/srs/review",
                       json={"item_type": "vocab", "item_id": v.id,
                             "grade": "good"})
    assert resp.status_code == 200
    db_session.refresh(progress)
    assert progress.interval_days == 1 and progress.reps == 1


def test_review_rejects_bad_grade(client, db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=date.today())
    db_session.add(v)
    db_session.commit()
    resp = client.post("/api/srs/review",
                       json={"item_type": "vocab", "item_id": v.id,
                             "grade": "perfect"})
    assert resp.status_code == 422
