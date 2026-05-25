from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GrammarPoint
from app.services import grammar_quiz
from app.services.srs import MASTERED_INTERVAL

router = APIRouter(prefix="/api/grammar", tags=["grammar"])


@router.get("/checklist")
def checklist(db: Session = Depends(get_db)) -> dict:
    """内置语法清单，按 JLPT 等级分组，带掌握状态。"""
    points = (
        db.query(GrammarPoint)
        .filter_by(curated=True)
        .order_by(GrammarPoint.jlpt_level, GrammarPoint.id)
        .all()
    )
    grouped: dict[str, list[dict]] = {}
    for g in points:
        mastered = g.in_srs and g.interval_days >= MASTERED_INTERVAL
        grouped.setdefault(g.jlpt_level, []).append({
            "id": g.id, "key": g.key, "name": g.name,
            "explanation": g.explanation, "status": g.status,
            "in_srs": g.in_srs, "mastered": mastered,
        })
    return grouped


@router.get("/{grammar_id}/quiz")
def quiz(grammar_id: int, db: Session = Depends(get_db)) -> dict:
    gp = db.get(GrammarPoint, grammar_id)
    if gp is None:
        raise HTTPException(404, "语法点不存在")
    try:
        return grammar_quiz.get_quiz(db, gp)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
