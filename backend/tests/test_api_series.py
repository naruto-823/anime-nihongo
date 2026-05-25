from app.models import Series


def test_create_and_list_series(client, db_session):
    resp = client.post("/api/series", json={"title": "鬼灭之刃"})
    assert resp.status_code == 200
    sid = resp.json()["id"]

    listed = client.get("/api/series").json()
    assert any(s["id"] == sid and s["title"] == "鬼灭之刃" for s in listed)


def test_set_current_series(client, db_session):
    a = client.post("/api/series", json={"title": "A"}).json()["id"]
    b = client.post("/api/series", json={"title": "B"}).json()["id"]
    client.post(f"/api/series/{a}/set-current")
    client.post(f"/api/series/{b}/set-current")
    rows = {s.id: s.is_current for s in db_session.query(Series).all()}
    assert rows[a] is False and rows[b] is True  # 全局至多一个 current
