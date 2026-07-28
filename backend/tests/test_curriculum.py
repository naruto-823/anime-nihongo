import random

from app.models import CurriculumItem, GrammarPoint, UserItemMastery, Vocab
from app.services import tower
from app.services.curriculum import (
    backfill_legacy_mastery,
    coverage_report,
    record_mastery,
    sync_curriculum,
    vocab_dimensions,
)


def _seed(db):
    db.add_all([
        Vocab(headword="猫", reading="ねこ", meaning_zh="猫", pos="名", jlpt_level="N5"),
        Vocab(headword="飲む", reading="のむ", meaning_zh="喝", pos="他動1", jlpt_level="N5"),
        Vocab(headword="ありがとう", reading="ありがとう", meaning_zh="谢谢", pos="感", jlpt_level="N5"),
        GrammarPoint(key="N5-test", name="〜ている", jlpt_level="N5",
                     explanation="正在做某事", curated=True),
    ])
    db.commit()


def test_sync_curriculum_maps_every_seeded_item(db_session):
    _seed(db_session)
    assert sync_curriculum(db_session) == 4
    assert sync_curriculum(db_session) == 0
    report = coverage_report(db_session, 1)
    n5 = report["levels"][0]
    assert report["syllabus_complete"] is True
    assert n5["vocab"] == {"total": 3, "mapped": 3}
    assert n5["grammar"] == {"total": 1, "mapped": 1}
    assert db_session.query(CurriculumItem).count() == 4


def test_required_dimensions_match_supported_question_types(db_session):
    _seed(db_session)
    items = db_session.query(Vocab).order_by(Vocab.id).all()
    assert vocab_dimensions(items[0]) == ["meaning", "recall", "reading"]
    assert "conjugation" in vocab_dimensions(items[1])
    assert vocab_dimensions(items[2]) == ["meaning", "recall"]


def test_quiz_rotates_to_least_practiced_dimension(db_session):
    _seed(db_session)
    sync_curriculum(db_session)
    vocab = db_session.query(Vocab).first()
    record_mastery(db_session, 1, "vocab", vocab.id, "meaning", True)
    db_session.commit()
    questions = tower.build_quiz(db_session, "N5", 0, 0, False, random.Random(1), 1)
    question = next(q for q in questions if q["item"]["kind"] == "vocab"
                    and q["item"]["id"] == vocab.id)
    assert question["item"]["dimension"] == "recall"


def test_submission_records_per_user_dimension_evidence(db_session):
    _seed(db_session)
    sync_curriculum(db_session)
    vocab = db_session.query(Vocab).first()
    tower.submit_result(db_session, "N5", 0, 0, False, [{
        "item": {"kind": "vocab", "id": vocab.id, "dimension": "recall"},
        "correct": True,
    }], user_id=1)
    evidence = db_session.query(UserItemMastery).one()
    assert (evidence.user_id, evidence.dimension, evidence.attempts,
            evidence.correct, evidence.mastery) == (1, "recall", 1, 1, 1.0)
    report = coverage_report(db_session, 1)
    assert report["totals"]["practiced_dimensions"] == 1
    assert report["totals"]["mastered_dimensions"] == 1


def test_legacy_progress_becomes_practiced_not_fake_mastery(db_session):
    from app.models import UserVocabProgress

    _seed(db_session)
    vocab = db_session.query(Vocab).first()
    db_session.add(UserVocabProgress(user_id=1, vocab_id=vocab.id, in_srs=True,
                                     reps=0, lapses=0))
    db_session.commit()
    assert backfill_legacy_mastery(db_session) == 1
    assert backfill_legacy_mastery(db_session) == 0
    evidence = db_session.query(UserItemMastery).one()
    assert evidence.attempts == 1
    assert evidence.correct == 0
    assert evidence.mastery == 0.0
