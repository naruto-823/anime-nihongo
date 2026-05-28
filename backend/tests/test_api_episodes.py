from pathlib import Path

from app.services import pipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_file_creates_episode(client, db_session, monkeypatch):
    import json as _json
    from tests.test_pipeline import _fake_llm

    _calls = {"n": 0}

    def _scene_aware_llm(system, user, model=None, max_tokens=8000):
        _calls["n"] += 1
        if _calls["n"] == 1:
            # Scene-split call — return two scenes covering 2 lines
            return {"scenes": [{"title_zh": "場面", "start_idx": 0, "end_idx": 1}]}
        return _fake_llm(system, user, model, max_tokens)

    monkeypatch.setattr(pipeline.llm, "call_json", _scene_aware_llm)

    sid = client.post("/api/series", json={"title": "测试番"}).json()["id"]
    with open(FIXTURES / "sample.srt", "rb") as f:
        resp = client.post(
            "/api/episodes/import-file",
            data={"series_id": str(sid), "number": "1"},
            files={"file": ("sample.srt", f, "text/plain")},
        )
    assert resp.status_code == 200
    ep = resp.json()
    assert ep["total_lines"] == 2

    detail = client.get(f"/api/episodes/{ep['id']}").json()
    assert detail["status"] == "ready"

    lines = client.get(f"/api/episodes/{ep['id']}/lines").json()
    assert len(lines) == 2
    assert lines[0]["text_jp"] == "おはよう、元気？"
    assert lines[0]["processed"] is True


def test_generate_demo(client, db_session, monkeypatch):
    from app.services import pipeline
    from app.services import llm as llm_mod
    from tests.test_pipeline import _fake_llm

    sid = client.post("/api/series", json={"title": "测试番"}).json()["id"]

    call_count = {"n": 0}
    def demo_then_pipeline_llm(system, user, model=None, max_tokens=8000):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"lines": [
                {"speaker": "A", "text": "おはよう"},
                {"speaker": "B", "text": "元気か？"},
            ]}
        if call_count["n"] == 2:
            # Scene-split call — return one scene covering 2 lines
            return {"scenes": [{"title_zh": "場面", "start_idx": 0, "end_idx": 1}]}
        return _fake_llm(system, user, model, max_tokens)

    monkeypatch.setattr(llm_mod, "call_json", demo_then_pipeline_llm)
    monkeypatch.setattr(pipeline.llm, "call_json", demo_then_pipeline_llm)

    resp = client.post("/api/episodes/generate-demo",
                       json={"series_id": sid, "number": 1, "lines_count": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["total_lines"] == 2
