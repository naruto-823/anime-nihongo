from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Episode, GrammarPoint, Vocab
from app.services import session as sess

router = APIRouter(prefix="/api/study", tags=["study"])


@router.post("/vocab/{vocab_id}/add-srs")
def add_vocab(vocab_id: int, db: Session = Depends(get_db)) -> dict:
    v = db.get(Vocab, vocab_id)
    if v is None:
        raise HTTPException(404, "词条不存在")
    v.in_srs = True
    if v.due_date is None:
        v.due_date = date.today()
    db.commit()
    return {"id": v.id, "in_srs": True}


@router.post("/grammar/{grammar_id}/add-srs")
def add_grammar(grammar_id: int, db: Session = Depends(get_db)) -> dict:
    gp = db.get(GrammarPoint, grammar_id)
    if gp is None:
        raise HTTPException(404, "语法点不存在")
    gp.in_srs = True
    gp.status = "learning"
    if gp.due_date is None:
        gp.due_date = date.today()
    db.commit()
    return {"id": gp.id, "in_srs": True, "status": gp.status}


class ReadingProgress(BaseModel):
    position: int


@router.post("/episodes/{episode_id}/reading-progress")
def reading_progress(episode_id: int, body: ReadingProgress,
                     db: Session = Depends(get_db)) -> dict:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    ep.read_position = body.position
    if body.position >= ep.total_lines:
        ep.reading_done = True
    db.commit()
    return {"id": ep.id, "read_position": ep.read_position,
            "reading_done": ep.reading_done}


class CompleteToday(BaseModel):
    episode_id: int | None = None
    vocab_reviewed: int = 0
    grammar_reviewed: int = 0
    lines_read: int = 0
    conversation_turns: int = 0
    summary: dict | None = None


@router.post("/complete-today")
def complete_today(body: CompleteToday, db: Session = Depends(get_db)) -> dict:
    today_d = date.today()
    stats = body.model_dump(exclude={"episode_id"}, exclude_none=True)
    sess.record_completion(db, today_d, body.episode_id, stats)
    return {"streak": sess.compute_streak(db, today_d)}
