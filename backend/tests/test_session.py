from datetime import date, timedelta

from app.models import DailySession, Episode, GrammarPoint, Series, Vocab
from app.services import session as sess


def test_current_episode_picks_current_series_unfinished(db_session):
    s = Series(title="番A", is_current=True)
    _done = Episode(series=s, number=1, source="upload", status="ready",
                    reading_done=True)
    _cur = Episode(series=s, number=2, source="upload", status="ready",
                   reading_done=False)
    db_session.add(s)
    db_session.commit()
    ep = sess.current_episode(db_session)
    assert ep is not None and ep.number == 2


def test_due_counts(db_session):
    today = date(2026, 5, 22)
    db_session.add_all([
        Vocab(headword="A", reading="あ", meaning_zh="a", in_srs=True,
              due_date=today),
        Vocab(headword="B", reading="び", meaning_zh="b", in_srs=True,
              due_date=today + timedelta(days=3)),  # 未到期
        GrammarPoint(key="g1", name="g1", jlpt_level="N2", explanation="x",
                     in_srs=True, due_date=today - timedelta(days=1)),
    ])
    db_session.commit()
    counts = sess.due_counts(db_session, today)
    assert counts["vocab"] == 1
    assert counts["grammar"] == 1


def test_compute_streak(db_session):
    today = date(2026, 5, 22)
    for d in (today, today - timedelta(days=1), today - timedelta(days=2)):
        db_session.add(DailySession(date=d, completed=True))
    db_session.add(DailySession(date=today - timedelta(days=4), completed=True))
    db_session.commit()
    assert sess.compute_streak(db_session, today) == 3


def test_record_completion_upserts(db_session):
    today = date(2026, 5, 22)
    sess.record_completion(db_session, today, episode_id=None,
                           stats={"vocab_reviewed": 5})
    row = db_session.query(DailySession).filter_by(date=today).one()
    assert row.completed is True and row.vocab_reviewed == 5
    # 再次调用：更新而非重复插入
    sess.record_completion(db_session, today, episode_id=None,
                           stats={"vocab_reviewed": 9})
    assert db_session.query(DailySession).filter_by(date=today).count() == 1
    assert db_session.query(DailySession).filter_by(date=today).one().vocab_reviewed == 9
