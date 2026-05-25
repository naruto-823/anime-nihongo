from datetime import date, timedelta

from app.models import DailySession, GrammarPoint, Vocab


def test_progress_summary(client, db_session):
    today = date.today()
    db_session.add_all([
        DailySession(date=today, completed=True),
        DailySession(date=today - timedelta(days=1), completed=True),
        Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=today),
        GrammarPoint(key="g1", name="g1", jlpt_level="N2", explanation="x",
                     curated=True, in_srs=True, interval_days=30),
        GrammarPoint(key="g2", name="g2", jlpt_level="N2", explanation="y",
                     curated=True),
    ])
    db_session.commit()
    body = client.get("/api/progress").json()
    assert body["streak"] == 2
    assert body["vocab"]["in_srs"] == 1
    assert body["grammar"]["mastered"] == 1
    assert body["grammar"]["total_curated"] == 2
    assert len(body["history"]) == 2
