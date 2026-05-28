from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api._scene import build_scene_list
from app.db import get_db
from app.models import Series
from app.services import session as sess

router = APIRouter(prefix="/api/today", tags=["today"])


def _pick_main_character(s: Series) -> dict:
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
        "anilist_status": s.anilist_status,
        "main_character": _pick_main_character(s),
    }

    ep = sess.current_episode(db)
    if ep is None or ep.series_id != s.id:
        return {"streak": streak, "due_total": due_total,
                "series": series_block, "current_episode": None, "scenes": []}

    scene_out = build_scene_list(db, ep.id, ep.read_position)
    completed = sum(1 for sc in scene_out if sc["state"] == "done")
    total_scenes = len(scene_out)

    return {
        "streak": streak, "due_total": due_total,
        "series": series_block,
        "current_episode": {
            "id": ep.id, "number": ep.number, "title": ep.title,
            "read_position": ep.read_position, "total_lines": ep.total_lines,
            "completed_scenes": completed, "total_scenes": total_scenes,
            "status": ep.status,
        },
        "scenes": scene_out,
    }
