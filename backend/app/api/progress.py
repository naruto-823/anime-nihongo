from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DailySession, GrammarPoint, Vocab
from app.services.session import compute_streak
from app.services.srs import MASTERED_INTERVAL

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("")
def progress(db: Session = Depends(get_db)) -> dict:
    today = date.today()
    vocab_in_srs = db.query(Vocab).filter(Vocab.in_srs.is_(True)).count()
    vocab_total = db.query(Vocab).count()
    curated = db.query(GrammarPoint).filter_by(curated=True).count()
    seen = (
        db.query(GrammarPoint)
        .filter(GrammarPoint.curated.is_(True),
                GrammarPoint.status.in_(("seen", "learning")))
        .count()
    )
    mastered = (
        db.query(GrammarPoint)
        .filter(GrammarPoint.in_srs.is_(True),
                GrammarPoint.interval_days >= MASTERED_INTERVAL)
        .count()
    )
    history = [
        {"date": r.date.isoformat(), "completed": r.completed,
         "vocab_reviewed": r.vocab_reviewed,
         "grammar_reviewed": r.grammar_reviewed,
         "lines_read": r.lines_read}
        for r in db.query(DailySession).order_by(DailySession.date.desc()).all()
    ]
    return {
        "streak": compute_streak(db, today),
        "vocab": {"total": vocab_total, "in_srs": vocab_in_srs},
        "grammar": {"total_curated": curated, "encountered": seen,
                    "mastered": mastered},
        "history": history,
    }
