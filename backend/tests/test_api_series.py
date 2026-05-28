from unittest.mock import patch

from app.models import Series


def test_create_and_list_series(client, db_session):
    with patch("app.api.series.fetch_series_metadata", lambda t, http=None: None):
        resp = client.post("/api/series", json={"title": "鬼灭之刃"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "鬼灭之刃"
    assert body["anilist_status"] == "pending"
    assert body["anilist_id"] is None
    assert body["characters"] is None

    listed = client.get("/api/series").json()
    assert any(s["id"] == body["id"] for s in listed)


def test_set_current_series(client, db_session):
    with patch("app.api.series.fetch_series_metadata", lambda t, http=None: None):
        a = client.post("/api/series", json={"title": "A"}).json()["id"]
        b = client.post("/api/series", json={"title": "B"}).json()["id"]
    client.post(f"/api/series/{a}/set-current")
    client.post(f"/api/series/{b}/set-current")
    rows = {s.id: s.is_current for s in db_session.query(Series).all()}
    assert rows[a] is False and rows[b] is True


def test_create_series_triggers_anilist_background(client, db_session):
    captured = {}

    def fake_fetch(title, http=None):
        captured["title"] = title
        return {"anilist_id": 130003, "characters": [
            {"name_en": "Hitori Gotoh", "name_jp": "後藤ひとり",
             "image_url": "https://x/h.png", "role": "MAIN"}]}

    with patch("app.api.series.fetch_series_metadata", fake_fetch):
        resp = client.post("/api/series", json={"title": "Bocchi the Rock"})

    assert resp.status_code == 200
    sid = resp.json()["id"]
    db_session.expire_all()
    s = db_session.get(Series, sid)
    assert s.anilist_status == "matched"
    assert s.anilist_id == 130003
    assert s.characters[0]["name_jp"] == "後藤ひとり"
    assert captured["title"] == "Bocchi the Rock"


def test_create_series_anilist_not_found(client, db_session):
    with patch("app.api.series.fetch_series_metadata", lambda t, http=None: None):
        sid = client.post("/api/series", json={"title": "no-such"}).json()["id"]
    db_session.expire_all()
    assert db_session.get(Series, sid).anilist_status == "not_found"


def test_create_series_anilist_error_marks_failed(client, db_session):
    from app.services.anilist import AniListError

    def boom(title, http=None):
        raise AniListError("upstream down")

    with patch("app.api.series.fetch_series_metadata", boom):
        sid = client.post("/api/series", json={"title": "X"}).json()["id"]
    db_session.expire_all()
    assert db_session.get(Series, sid).anilist_status == "failed"


def test_get_series_detail_includes_anilist_fields(client, db_session):
    s = Series(title="A", anilist_id=42, anilist_status="matched",
               characters=[{"name_en": "C", "name_jp": None,
                            "image_url": "https://x/c.png", "role": "MAIN"}])
    db_session.add(s); db_session.commit()
    body = client.get(f"/api/series/{s.id}").json()
    assert body["anilist_status"] == "matched"
    assert body["anilist_id"] == 42
    assert body["characters"][0]["image_url"] == "https://x/c.png"


def test_refresh_anilist_endpoint(client, db_session):
    s = Series(title="A", anilist_status="not_found")
    db_session.add(s); db_session.commit()

    def fake(title, http=None):
        return {"anilist_id": 1, "characters": []}

    with patch("app.api.series.fetch_series_metadata", fake):
        resp = client.post(f"/api/series/{s.id}/refresh-anilist")
    assert resp.status_code == 200
    assert resp.json()["anilist_status"] == "matched"
    db_session.expire_all()
    assert db_session.get(Series, s.id).anilist_id == 1


def test_refresh_anilist_error_marks_failed(client, db_session):
    from app.services.anilist import AniListError
    s = Series(title="A", anilist_status="matched"); db_session.add(s); db_session.commit()

    def boom(title, http=None):
        raise AniListError("down")

    with patch("app.api.series.fetch_series_metadata", boom):
        resp = client.post(f"/api/series/{s.id}/refresh-anilist")
    assert resp.status_code == 200
    assert resp.json()["anilist_status"] == "failed"


def test_search_jimaku_route_not_shadowed_by_series_id(client, db_session):
    # /search-jimaku must be matched before /{series_id:int}.
    # Without a token it returns 400; the bug would make it 422 (int parse).
    resp = client.get("/api/series/search-jimaku", params={"query": "x"})
    assert resp.status_code != 422
    assert resp.status_code in (200, 400, 502)
