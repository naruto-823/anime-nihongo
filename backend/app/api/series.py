import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.models import Series
from app.services.anilist import AniListError, fetch_series_metadata
from app.services.jimaku import JimakuClient, JimakuError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/series", tags=["series"])


class SeriesCreate(BaseModel):
    title: str
    title_jp: str | None = None
    jimaku_entry_id: int | None = None


def _series_dict(s: Series) -> dict:
    return {
        "id": s.id, "title": s.title, "title_jp": s.title_jp,
        "jimaku_entry_id": s.jimaku_entry_id, "is_current": s.is_current,
        "anilist_id": s.anilist_id, "anilist_status": s.anilist_status,
        "characters": s.characters,
    }


def _run_anilist_lookup(series_id: int, title: str) -> None:
    """后台任务：拉 AniList 并写回 Series。绝不让异常逃出。

    刻意自建 Session（不复用请求级 session）：BackgroundTasks 在响应发回后才跑，
    请求级 session 已关闭。
    """
    db = SessionLocal()
    try:
        try:
            result = fetch_series_metadata(title)
        except AniListError as exc:
            logger.warning("AniList lookup failed for %r: %s", title, exc)
            s = db.get(Series, series_id)
            if s is not None:
                s.anilist_status = "failed"
                db.commit()
            return
        s = db.get(Series, series_id)
        if s is None:
            return
        if result is None:
            s.anilist_status = "not_found"
        else:
            s.anilist_id = result["anilist_id"]
            s.characters = result["characters"]
            s.anilist_status = "matched"
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("AniList background task crashed for series %s", series_id)
    finally:
        db.close()


@router.get("")
def list_series(db: Session = Depends(get_db)) -> list[dict]:
    return [_series_dict(s) for s in db.query(Series).order_by(Series.id).all()]


@router.post("")
def create_series(body: SeriesCreate, bg: BackgroundTasks,
                  db: Session = Depends(get_db)) -> dict:
    s = Series(title=body.title, title_jp=body.title_jp,
               jimaku_entry_id=body.jimaku_entry_id)
    db.add(s)
    db.commit()
    bg.add_task(_run_anilist_lookup, s.id, s.title)
    return _series_dict(s)


@router.get("/search-jimaku")
def search_jimaku(query: str) -> list[dict]:
    if not settings.jimaku_api_token:
        raise HTTPException(400, "未配置 JIMAKU_API_TOKEN")
    try:
        return JimakuClient(settings.jimaku_api_token).search_entries(query)
    except JimakuError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/{series_id}")
def get_series(series_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.get(Series, series_id)
    if s is None:
        raise HTTPException(404, "番剧不存在")
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


@router.post("/{series_id}/refresh-anilist")
def refresh_anilist(series_id: int, db: Session = Depends(get_db)) -> dict:
    """同步重跑 AniList 查询。错误转 anilist_status=failed，HTTP 仍 200。"""
    s = db.get(Series, series_id)
    if s is None:
        raise HTTPException(404, "番剧不存在")
    try:
        result = fetch_series_metadata(s.title)
    except AniListError as exc:
        logger.warning("AniList refresh failed for %r: %s", s.title, exc)
        s.anilist_status = "failed"
        db.commit()
        return _series_dict(s)
    if result is None:
        s.anilist_status = "not_found"
    else:
        s.anilist_id = result["anilist_id"]
        s.characters = result["characters"]
        s.anilist_status = "matched"
    db.commit()
    return _series_dict(s)
