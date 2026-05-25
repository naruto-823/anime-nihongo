from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import DailySession, Episode, GrammarPoint, Series, Vocab

_STAT_FIELDS = ("vocab_reviewed", "grammar_reviewed", "lines_read",
                "conversation_turns")


def current_episode(session: Session) -> Episode | None:
    """当前主攻番里、最该推进的一集：优先精读未完成、集数最小者；否则集数最大者。"""
    series = session.query(Series).filter_by(is_current=True).first()
    if series is None:
        return None
    episodes = (
        session.query(Episode)
        .filter_by(series_id=series.id, status="ready")
        .order_by(Episode.number)
        .all()
    )
    if not episodes:
        return None
    unfinished = [e for e in episodes if not e.reading_done]
    return unfinished[0] if unfinished else episodes[-1]


def due_counts(session: Session, today: date) -> dict:
    """到期待复习的词汇 / 语法数量。"""
    vocab = (
        session.query(Vocab)
        .filter(Vocab.in_srs.is_(True), Vocab.due_date <= today)
        .count()
    )
    grammar = (
        session.query(GrammarPoint)
        .filter(GrammarPoint.in_srs.is_(True), GrammarPoint.due_date <= today)
        .count()
    )
    return {"vocab": vocab, "grammar": grammar}


def compute_streak(session: Session, today: date) -> int:
    """连续打卡天数：从 today 往回数连续 completed 的 DailySession。"""
    completed = {
        r.date
        for r in session.query(DailySession).filter_by(completed=True).all()
    }
    streak = 0
    cursor = today
    while cursor in completed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def record_completion(session: Session, today: date, episode_id: int | None,
                       stats: dict) -> DailySession:
    """记录/更新今天的训练完成情况（按日期 upsert）。"""
    row = session.query(DailySession).filter_by(date=today).first()
    if row is None:
        row = DailySession(date=today)
        session.add(row)
    row.completed = True
    row.episode_id = episode_id
    for field in _STAT_FIELDS:
        if field in stats:
            setattr(row, field, stats[field])
    if "summary" in stats:
        row.summary = stats["summary"]
    session.commit()
    return row
