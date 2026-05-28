from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.episodes import _scene_dict, _scene_state
from app.db import get_db
from app.models import Line, Scene, Series
from app.services import session as sess

router = APIRouter(prefix="/api/today", tags=["today"])


def _pick_main_character(s: Series) -> dict | None:
    """按 spec §5.5：始终返回 {name_jp, name_en, image_url, fallback_initial}。
    没匹配 character 时 name/image 为 null，fallback_initial 取 series.title 首字符。"""
    chars = s.characters or []
    with_img = next((c for c in chars if c.get("image_url")), None)
    pick = with_img or (chars[0] if chars else None)
    if pick is None:
        first = (s.title or "?")[:1]
        return {"name_en": None, "name_jp": None, "image_url": None,
                "fallback_initial": first}
    name_jp = pick.get("name_jp")
    name_en = pick.get("name_en")
    fallback_source = name_jp or name_en or s.title or "?"
    return {
        "name_en": name_en, "name_jp": name_jp,
        "image_url": pick.get("image_url"),
        "fallback_initial": fallback_source[:1],
    }


@router.get("/journey")
def journey(db: Session = Depends(get_db)) -> dict:
    today_d = date.today()
    s = db.query(Series).filter_by(is_current=True).first()
    streak = sess.compute_streak(db, today_d)
    due = sess.due_counts(db, today_d)
    due_total = due["vocab"] + due["grammar"]

    if s is None:
        return {"streak": streak, "due_total": due_total,
                "series": None, "current_episode": None, "scenes": []}

    series_block = {
        "id": s.id, "title": s.title,
        "main_character": _pick_main_character(s),
    }

    ep = sess.current_episode(db)
    if ep is None or ep.series_id != s.id:
        return {"streak": streak, "due_total": due_total,
                "series": series_block, "current_episode": None, "scenes": []}

    scenes = (
        db.query(Scene).filter_by(episode_id=ep.id)
        .order_by(Scene.idx).all()
    )
    completed = sum(1 for sc in scenes if sc.end_line_idx < ep.read_position)

    scene_out: list[dict] = []
    for sc in scenes:
        state = _scene_state(sc, ep.read_position)
        preview = None
        if state == "current":
            lines = (
                db.query(Line).filter_by(episode_id=ep.id)
                .filter(Line.idx >= sc.start_line_idx,
                        Line.idx <= sc.end_line_idx)
                .order_by(Line.idx).limit(2).all()
            )
            preview = [ln.text_jp for ln in lines]
        scene_out.append(_scene_dict(sc, state, preview))

    return {
        "streak": streak, "due_total": due_total,
        "series": series_block,
        "current_episode": {
            "id": ep.id, "number": ep.number, "title": ep.title,
            "read_position": ep.read_position, "total_lines": ep.total_lines,
            "completed_scenes": completed, "total_scenes": len(scenes),
            "status": ep.status,
        },
        "scenes": scene_out,
    }
