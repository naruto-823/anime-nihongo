from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.api._scene import build_scene_list
from app.models import Episode, Line, Series
from app.services import llm, pipeline
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


_DEMO_SYSTEM = """\
你是动漫剧本作家。给定动漫名「{title}」第 {number} 集，请生成 {n} 行符合该番作品风格的日语对白。
只返回 JSON 对象，不要多余文字。结构：
{{"lines": [{{"speaker": "角色名（可省略）", "text": "日语台词"}}, ...]}}
要求：
- 必须 {n} 行；每行台词长度 8–30 个字符；台词自然口语化、不要旁白。
- 风格符合该番（动作/校园/异世界/搞笑等）；若是知名番剧，用其标志性人物与情节元素。
- 语法分布：故意覆盖一些 N2/N1 句型（〜ばかりか、〜にもかかわらず、〜ざるを得ない、〜つつ、〜どころか 等），让台词成为有学习价值的素材。
- 男女角色对白穿插，体现普通体/丁宁体差异。\
"""


class GenerateDemo(BaseModel):
    series_id: int
    number: int
    lines_count: int = 20


@router.post("/generate-demo")
def generate_demo(body: GenerateDemo, db: Session = Depends(get_db)) -> dict:
    series = db.get(Series, body.series_id)
    if series is None:
        raise HTTPException(404, "番剧不存在")
    if db.query(Episode).filter_by(series_id=body.series_id, number=body.number).first():
        raise HTTPException(409, f"第 {body.number} 集已存在")
    system = _DEMO_SYSTEM.format(title=series.title, number=body.number, n=body.lines_count)
    result = llm.call_json(system=system, user="请按要求生成。")
    raw = result.get("lines") or []
    if not raw:
        raise HTTPException(502, "LLM 未返回任何台词")
    ep = Episode(series_id=body.series_id, number=body.number, source="generated",
                 status="processing", total_lines=len(raw))
    for i, ln in enumerate(raw):
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        ep.lines.append(Line(idx=len(ep.lines), text_jp=text,
                             speaker=(ln.get("speaker") or None), processed=False))
    if not ep.lines:
        raise HTTPException(502, "LLM 返回的台词全部为空")
    ep.total_lines = len(ep.lines)
    db.add(ep)
    db.commit()
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


@router.get("/{episode_id}/scenes")
def get_scenes(episode_id: int, db: Session = Depends(get_db)) -> list[dict]:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    if not ep.scenes_split or ep.status != "ready":
        return []
    return build_scene_list(db, episode_id, ep.read_position)
