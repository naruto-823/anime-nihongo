from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import current_user_id
from app.db import get_db
from app.models import GrammarPoint, Line, UserGrammarProgress, UserVocabProgress, Vocab
from app.services.srs import apply_review

router = APIRouter(prefix="/api/srs", tags=["srs"])


@router.get("/due")
def due(db: Session = Depends(get_db), user_id: int = Depends(current_user_id)) -> dict:
    today = date.today()
    vocab = (
        db.query(Vocab)
        .join(UserVocabProgress, UserVocabProgress.vocab_id == Vocab.id)
        .filter(UserVocabProgress.user_id == user_id,
                UserVocabProgress.in_srs.is_(True), UserVocabProgress.due_date <= today)
        .order_by(UserVocabProgress.due_date)
        .all()
    )
    grammar = (
        db.query(GrammarPoint)
        .join(UserGrammarProgress, UserGrammarProgress.grammar_id == GrammarPoint.id)
        .filter(UserGrammarProgress.user_id == user_id,
                UserGrammarProgress.in_srs.is_(True), UserGrammarProgress.due_date <= today)
        .order_by(UserGrammarProgress.due_date)
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
def review(body: ReviewBody, db: Session = Depends(get_db),
           user_id: int = Depends(current_user_id)) -> dict:
    content_model = Vocab if body.item_type == "vocab" else GrammarPoint
    progress_model = UserVocabProgress if body.item_type == "vocab" else UserGrammarProgress
    item_field = "vocab_id" if body.item_type == "vocab" else "grammar_id"
    if db.get(content_model, body.item_id) is None:
        raise HTTPException(404, "复习项不存在")
    item = db.query(progress_model).filter_by(user_id=user_id, **{item_field: body.item_id}).one_or_none()
    if item is None:
        raise HTTPException(409, "该项目尚未加入复习")
    apply_review(item, body.grade)
    db.commit()
    return {"id": item.id, "interval_days": item.interval_days,
            "reps": item.reps, "due_date": item.due_date.isoformat()}
