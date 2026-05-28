import json

import pytest

from app.grammar_loader import load_grammar_seed
from app.models import Episode, Line, Scene, Series
from app.services import pipeline


def _make_episode(db_session, n_lines: int):
    s = Series(title="番")
    e = Episode(series=s, number=1, source="upload", status="processing",
                total_lines=n_lines)
    for i in range(n_lines):
        e.lines.append(Line(idx=i, text_jp=f"行{i}", processed=False))
    db_session.add(s)
    db_session.commit()
    return e


def _route_llm(split_response, *, annotate=None):
    """返回一个假 llm.call_json：第一次（切场景）返回 split_response，
    之后（注标）按 annotate 函数回填。annotate=None 时返回最小合法注标。"""
    state = {"calls": 0}

    def fake(system, user, model=None, max_tokens=4000):
        state["calls"] += 1
        if state["calls"] == 1:
            return split_response
        if annotate is not None:
            return annotate(system, user)
        # 默认注标：按 user 里 idx 回填空注释
        payload = json.loads(user)
        return {"lines": [{"idx": ln["idx"], "translation_zh": "",
                           "grammar_notes": [], "register_tag": "casual",
                           "grammar_point_keys": []} for ln in payload["lines"]],
                "vocab": []}

    fake.state = state
    return fake


def test_splits_scenes_writes_rows_and_flips_flag(db_session, monkeypatch):
    load_grammar_seed(db_session)
    ep = _make_episode(db_session, 30)
    split = {"scenes": [
        {"title_zh": "开场", "start_idx": 0, "end_idx": 9},
        {"title_zh": "冲突", "start_idx": 10, "end_idx": 19},
        {"title_zh": "结尾", "start_idx": 20, "end_idx": 29},
    ]}
    monkeypatch.setattr(pipeline.llm, "call_json", _route_llm(split))

    pipeline.process_episode(db_session, ep.id, batch_size=100)

    db_session.refresh(ep)
    assert ep.scenes_split is True
    assert ep.status == "ready"
    scenes = db_session.query(Scene).filter_by(episode_id=ep.id).order_by(Scene.idx).all()
    assert [s.title_zh for s in scenes] == ["开场", "冲突", "结尾"]
    assert [(s.start_line_idx, s.end_line_idx) for s in scenes] == [
        (0, 9), (10, 19), (20, 29),
    ]
    assert [s.line_count for s in scenes] == [10, 10, 10]


@pytest.mark.parametrize("bad_scenes,reason", [
    ({"scenes": []}, "empty"),
    ({"scenes": [{"title_zh": "A", "start_idx": 0, "end_idx": 4},
                 {"title_zh": "B", "start_idx": 6, "end_idx": 9}]}, "gap"),
    ({"scenes": [{"title_zh": "A", "start_idx": 0, "end_idx": 6},
                 {"title_zh": "B", "start_idx": 5, "end_idx": 9}]}, "overlap"),
    ({"scenes": [{"title_zh": "A", "start_idx": 0, "end_idx": 5}]},
     "incomplete"),
    ({"scenes": [{"title_zh": "", "start_idx": 0, "end_idx": 9}]}, "empty-title"),
])
def test_split_validation_failures_mark_episode_failed(
        db_session, monkeypatch, bad_scenes, reason):
    load_grammar_seed(db_session)
    ep = _make_episode(db_session, 10)
    monkeypatch.setattr(pipeline.llm, "call_json", _route_llm(bad_scenes))

    with pytest.raises(ValueError):
        pipeline.process_episode(db_session, ep.id, batch_size=100)

    db_session.refresh(ep)
    assert ep.status == "failed", f"reason={reason}"
    assert ep.scenes_split is False
    assert db_session.query(Scene).filter_by(episode_id=ep.id).count() == 0


def test_does_not_resplit_when_already_split(db_session, monkeypatch):
    load_grammar_seed(db_session)
    ep = _make_episode(db_session, 10)
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="预存",
                         start_line_idx=0, end_line_idx=9, line_count=10))
    ep.scenes_split = True
    db_session.commit()

    fake = _route_llm({"scenes": [
        {"title_zh": "不应被使用", "start_idx": 0, "end_idx": 9}]})
    monkeypatch.setattr(pipeline.llm, "call_json", fake)

    pipeline.process_episode(db_session, ep.id, batch_size=100)

    titles = [s.title_zh for s in
              db_session.query(Scene).filter_by(episode_id=ep.id).order_by(Scene.idx)]
    assert titles == ["预存"]
