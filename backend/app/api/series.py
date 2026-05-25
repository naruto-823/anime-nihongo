from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Series
from app.services.jimaku import JimakuClient, JimakuError

router = APIRouter(prefix="/api/series", tags=["series"])


class SeriesCreate(BaseModel):
    title: str
    title_jp: str | None = None
    jimaku_entry_id: int | None = None


def _series_dict(s: Series) -> dict:
    return {"id": s.id, "title": s.title, "title_jp": s.title_jp,
            "jimaku_entry_id": s.jimaku_entry_id, "is_current": s.is_current}


@router.get("")
def list_series(db: Session = Depends(get_db)) -> list[dict]:
    return [_series_dict(s) for s in db.query(Series).order_by(Series.id).all()]


@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db)) -> dict:
    s = Series(title=body.title, title_jp=body.title_jp,
               jimaku_entry_id=body.jimaku_entry_id)
    db.add(s)
    db.commit()
    return _series_dict(s)


@router.post("/{series_id}/set-current")
def set_current(series_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.get(Series, series_id)
    if s is None:
        raise HTTPException(404, "番剧不存在")
    for other in db.query(Series).filter(Series.is_current.is_(True)).all():
        other.is_current = False
    s.is_current = True
    db.commit()
    return _series_dict(s)


@router.get("/search-jimaku")
def search_jimaku(query: str) -> list[dict]:
    if not settings.jimaku_api_token:
        raise HTTPException(400, "未配置 JIMAKU_API_TOKEN")
    try:
        return JimakuClient(settings.jimaku_api_token).search_entries(query)
    except JimakuError as exc:
        raise HTTPException(502, str(exc)) from exc
