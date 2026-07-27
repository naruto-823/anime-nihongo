import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import current_user_id
from app.db import get_db
from app.models import PlayerStats
from app.services import tower
from app.services.tower import LockedStageError

router = APIRouter(tags=["tower"])


@router.get("/api/tower")
def get_tower(db: Session = Depends(get_db), user_id: int = Depends(current_user_id)) -> dict:
    return tower.tower_map(db, user_id)


@router.get("/api/tower/quiz")
def get_quiz(
    level: str = Query(...),
    zone: int = Query(0),
    stage: int = Query(0),
    boss: bool = Query(False),
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> dict:
    questions = tower.build_quiz(db, level, zone, stage, boss, random.Random())
    return {"questions": questions}


@router.get("/api/player")
def get_player(db: Session = Depends(get_db), user_id: int = Depends(current_user_id)) -> dict:
    p = db.get(PlayerStats, user_id)
    return {"total_xp": p.total_xp if p else 0,
            "player_level": p.player_level if p else 1}


class QItem(BaseModel):
    kind: str
    id: int


class QResult(BaseModel):
    item: QItem
    correct: bool


class SubmitBody(BaseModel):
    level: str
    zone: int = 0
    stage: int = 0
    boss: bool = False
    results: list[QResult]


@router.post("/api/tower/submit")
def submit(body: SubmitBody, db: Session = Depends(get_db),
           user_id: int = Depends(current_user_id)) -> dict:
    results = [{"item": {"kind": r.item.kind, "id": r.item.id}, "correct": r.correct}
               for r in body.results]
    try:
        return tower.submit_result(db, body.level, body.zone, body.stage, body.boss,
                                   results, user_id=user_id)
    except LockedStageError:
        raise HTTPException(status_code=403, detail="关卡未解锁")
