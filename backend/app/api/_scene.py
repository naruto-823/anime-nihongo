"""场景序列化共享逻辑：被 episodes 和 today 两个路由复用。"""
from sqlalchemy.orm import Session

from app.models import Line, Scene


def scene_state(scene: Scene, read_position: int) -> str:
    if scene.end_line_idx < read_position:
        return "done"
    if scene.start_line_idx <= read_position <= scene.end_line_idx:
        return "current"
    return "locked"


def scene_dict(scene: Scene, state: str, preview: list[str] | None = None) -> dict:
    if state == "locked":
        return {"id": scene.id, "idx": scene.idx, "state": "locked",
                "title_zh": None, "line_count": None,
                "start_line_idx": None, "end_line_idx": None}
    out = {
        "id": scene.id, "idx": scene.idx, "state": state,
        "title_zh": scene.title_zh, "line_count": scene.line_count,
        "start_line_idx": scene.start_line_idx, "end_line_idx": scene.end_line_idx,
    }
    if state == "current" and preview is not None:
        out["preview_lines"] = preview
    return out


def build_scene_list(db: Session, episode_id: int, read_position: int) -> list[dict]:
    """取一集的全部场景，算三态，current 场附前 2 行 preview。"""
    scenes = (
        db.query(Scene).filter_by(episode_id=episode_id)
        .order_by(Scene.idx).all()
    )
    out: list[dict] = []
    for sc in scenes:
        state = scene_state(sc, read_position)
        preview = None
        if state == "current":
            lines = (
                db.query(Line).filter_by(episode_id=episode_id)
                .filter(Line.idx >= sc.start_line_idx, Line.idx <= sc.end_line_idx)
                .order_by(Line.idx).limit(2).all()
            )
            preview = [ln.text_jp for ln in lines]
        out.append(scene_dict(sc, state, preview))
    return out
