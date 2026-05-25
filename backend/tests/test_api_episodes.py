from pathlib import Path

from app.services import pipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_file_creates_episode(client, db_session, monkeypatch):
    from tests.test_pipeline import _fake_llm
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)

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
