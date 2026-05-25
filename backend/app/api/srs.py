from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GrammarPoint, Line, Vocab
from app.services.srs import apply_review

router = APIRouter(prefix="/api/srs", tags=["srs"])


@router.get("/due")
def due(db: Session = Depends(get_db)) -> dict:
    today = date.today()
    vocab = (
        db.query(Vocab)
        .filter(Vocab.in_srs.is_(True), Vocab.due_date <= today)
        .order_by(Vocab.due_date)
        .all()
    )
    grammar = (
        db.query(GrammarPoint)
        .filter(GrammarPoint.in_srs.is_(True), GrammarPoint.due_date <= today)
        .order_by(GrammarPoint.due_date)
        .all()
    )
    vocab_out = []
    for v in vocab:
        line = db.get(Line, v.source_line_id) if v.source_line_id else None
        vocab_out.append({
            "id": v.id, "headword": v.headword, "reading": v.reading,
            "meaning_zh": v.meaning_zh, "pos": v.pos,
            "context": line.text_jp if line else None,
        })
    grammar_out = [
        {"id": g.id, "key": g.key, "name": g.name, "jlpt_level": g.jlpt_level,
         "explanation": g.explanation}
        for g in grammar
    ]
    return {"vocab": vocab_out, "grammar": grammar_out}


class ReviewBody(BaseModel):
    item_type: Literal["vocab", "grammar"]
    item_id: int
    grade: Literal["again", "hard", "good", "easy"]


@router.post("/review")
def review(body: ReviewBody, db: Session = Depends(get_db)) -> dict:
    model = Vocab if body.item_type == "vocab" else GrammarPoint
    item = db.get(model, body.item_id)
    if item is None:
        raise HTTPException(404, "复习项不存在")
    apply_review(item, body.grade)
    db.commit()
    return {"id": item.id, "interval_days": item.interval_days,
            "reps": item.reps, "due_date": item.due_date.isoformat()}
