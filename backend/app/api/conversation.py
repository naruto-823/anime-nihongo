from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Episode, GrammarPoint, Series, Vocab
from app.services import conversation

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


class Turn(BaseModel):
    episode_id: int
    character: str = "登場人物"
    history: list[dict] = []
    user_text: str


class Feedback(BaseModel):
    episode_id: int
    history: list[dict] = []


def _episode_ctx(db: Session, episode_id: int) -> tuple[str, int]:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    series = db.get(Series, ep.series_id)
    return (series.title if series else "动漫"), ep.number


@router.post("/turn")
def turn(body: Turn, db: Session = Depends(get_db)) -> dict:
    title, number = _episode_ctx(db, body.episode_id)
    return conversation.converse(
        series_title=title, episode_number=number, character=body.character,
        history=body.history, user_text=body.user_text)


@router.post("/feedback")
def feedback(body: Feedback, db: Session = Depends(get_db)) -> dict:
    title, number = _episode_ctx(db, body.episode_id)
    fb = conversation.conversation_feedback(
        series_title=title, episode_number=number, history=body.history)
    # 新词入库并加入 SRS
    for item in fb.get("new_vocab", []):
        hw, rd = item.get("headword"), item.get("reading")
        if not hw or not rd:
            continue
        existing = db.query(Vocab).filter_by(headword=hw, reading=rd).first()
        if existing is None:
            db.add(Vocab(headword=hw, reading=rd,
                         meaning_zh=item.get("meaning_zh", ""),
                         in_srs=True, due_date=date.today()))
        else:
            existing.in_srs = True
            if existing.due_date is None:
                existing.due_date = date.today()
    # 薄弱语法点加入 SRS
    for key in fb.get("weak_grammar_keys", []):
        gp = db.query(GrammarPoint).filter_by(key=key).first()
        if gp is not None:
            gp.in_srs = True
            gp.status = "learning"
            if gp.due_date is None:
                gp.due_date = date.today()
    db.commit()
    return fb
