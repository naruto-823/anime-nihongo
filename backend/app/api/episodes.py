from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Episode, Line, Series
from app.services import pipeline
from app.services.jimaku import JimakuClient, JimakuError
from app.services.subtitles import parse_subtitle

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


def _episode_dict(e: Episode) -> dict:
    return {"id": e.id, "series_id": e.series_id, "number": e.number,
            "title": e.title, "status": e.status,
            "total_lines": e.total_lines, "processed_lines": e.processed_lines,
            "read_position": e.read_position, "reading_done": e.reading_done}


def _line_dict(ln: Line) -> dict:
    return {"id": ln.id, "idx": ln.idx, "start_ms": ln.start_ms,
            "end_ms": ln.end_ms, "speaker": ln.speaker, "text_jp": ln.text_jp,
            "furigana": ln.furigana, "translation_zh": ln.translation_zh,
            "grammar_notes": ln.grammar_notes, "register_tag": ln.register_tag,
            "grammar_point_keys": ln.grammar_point_keys,
            "processed": ln.processed}


def _import_lines(db: Session, series_id: int, number: int,
                  source: str, content: str, fmt: str) -> Episode:
    parsed = parse_subtitle(content, fmt)
    if not parsed:
        raise HTTPException(400, "字幕未解析出任何台词")
    if db.get(Series, series_id) is None:
        raise HTTPException(404, "番剧不存在")
    if db.query(Episode).filter_by(series_id=series_id, number=number).first():
        raise HTTPException(409, f"第 {number} 集已存在")
    ep = Episode(series_id=series_id, number=number, source=source,
                 status="processing", total_lines=len(parsed))
    for p in parsed:
        ep.lines.append(Line(idx=p.idx, start_ms=p.start_ms, end_ms=p.end_ms,
                             speaker=p.speaker, text_jp=p.text, processed=False))
    db.add(ep)
    db.commit()
    return ep


@router.post("/import-file")
def import_file(series_id: int = Form(...), number: int = Form(...),
                file: UploadFile = File(...),
                db: Session = Depends(get_db)) -> dict:
    raw = file.file.read().decode("utf-8", errors="ignore")
    fmt = (file.filename or "x.srt").rsplit(".", 1)[-1]
    ep = _import_lines(db, series_id, number, "upload", raw, fmt)
    pipeline.process_episode(db, ep.id)
    db.refresh(ep)
    return _episode_dict(ep)


class JimakuImport(BaseModel):
    series_id: int
    number: int
    file_url: str


@router.post("/import-jimaku")
def import_jimaku(body: JimakuImport, db: Session = Depends(get_db)) -> dict:
    if not settings.jimaku_api_token:
        raise HTTPException(400, "未配置 JIMAKU_API_TOKEN")
    try:
        content = JimakuClient(settings.jimaku_api_token).download_file(body.file_url)
    except JimakuError as exc:
        raise HTTPException(502, str(exc)) from exc
    fmt = body.file_url.rsplit(".", 1)[-1]
    ep = _import_lines(db, body.series_id, body.number, "jimaku", content, fmt)
    pipeline.process_episode(db, ep.id)
    db.refresh(ep)
    return _episode_dict(ep)


@router.get("/{episode_id}")
def get_episode(episode_id: int, db: Session = Depends(get_db)) -> dict:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    return _episode_dict(ep)


@router.get("/{episode_id}/lines")
def get_lines(episode_id: int, db: Session = Depends(get_db)) -> list[dict]:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    lines = db.query(Line).filter_by(episode_id=episode_id).order_by(Line.idx).all()
    return [_line_dict(ln) for ln in lines]
