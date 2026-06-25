from app.models import Vocab


def _seed(db):
    db.add_all([
        Vocab(headword="元気", reading="げんき", meaning_zh="精神；健康", pos="名", jlpt_level="N5"),
        Vocab(headword="天気", reading="てんき", meaning_zh="天气", pos="名", jlpt_level="N5"),
        Vocab(headword="食べる", reading="たべる", meaning_zh="吃", pos="他動2", jlpt_level="N5"),
        Vocab(headword="経済", reading="けいざい", meaning_zh="经济", pos="名", jlpt_level="N2"),
    ])
    db.commit()


def test_list_returns_total_counts_items(client, db_session):
    _seed(db_session)
    body = client.get("/api/vocab").json()
    assert body["total"] == 4
    assert body["counts"]["N5"] == 3
    assert body["counts"]["N2"] == 1
    assert len(body["items"]) == 4
    assert {"id", "headword", "reading", "meaning_zh", "pos", "jlpt_level", "in_srs"} <= body["items"][0].keys()


def test_level_filter(client, db_session):
    _seed(db_session)
    body = client.get("/api/vocab?level=N5").json()
    assert body["total"] == 3
    assert all(it["jlpt_level"] == "N5" for it in body["items"])
    # counts 不受 level 影响，仍展示全部等级
    assert body["counts"]["N2"] == 1


def test_search_matches_headword_reading_meaning(client, db_session):
    _seed(db_session)
    assert client.get("/api/vocab?q=天気").json()["total"] == 1
    assert client.get("/api/vocab?q=てんき").json()["total"] == 1
    assert client.get("/api/vocab?q=经济").json()["total"] == 1
    # q 与 counts 联动
    assert client.get("/api/vocab?q=天気").json()["counts"]["N5"] == 1


def test_items_include_pos_tags(client, db_session):
    _seed(db_session)
    body = client.get("/api/vocab?q=食べる").json()
    item = body["items"][0]
    assert "pos_tags" in item
    assert "动词" in item["pos_tags"]


def test_pos_filter_verb(client, db_session):
    _seed(db_session)
    body = client.get("/api/vocab?pos=verb").json()
    assert body["total"] == 1
    assert body["items"][0]["headword"] == "食べる"


def test_pos_filter_noun(client, db_session):
    _seed(db_session)
    body = client.get("/api/vocab?pos=noun").json()
    assert body["total"] == 3
    assert all("名词" in it["pos_tags"] for it in body["items"])


def test_detail_returns_conjugation_for_verb(client, db_session):
    _seed(db_session)
    vid = client.get("/api/vocab?pos=verb").json()["items"][0]["id"]
    body = client.get(f"/api/vocab/{vid}").json()
    assert body["headword"] == "食べる"
    assert "动词" in body["pos_tags"]
    assert body["conjugation"]["group"] == "一段"
    keys = {f["key"] for f in body["conjugation"]["forms"]}
    assert {"te", "ta", "nai", "potential"} <= keys


def test_detail_noun_has_null_conjugation(client, db_session):
    _seed(db_session)
    nid = client.get("/api/vocab?pos=noun").json()["items"][0]["id"]
    body = client.get(f"/api/vocab/{nid}").json()
    assert body["conjugation"] is None


def test_detail_404(client, db_session):
    _seed(db_session)
    assert client.get("/api/vocab/99999").status_code == 404


def test_pagination(client, db_session):
    _seed(db_session)
    page1 = client.get("/api/vocab?limit=2&offset=0").json()
    page2 = client.get("/api/vocab?limit=2&offset=2").json()
    assert page1["total"] == 4 and page2["total"] == 4
    assert len(page1["items"]) == 2 and len(page2["items"]) == 2
    ids1 = {it["id"] for it in page1["items"]}
    ids2 = {it["id"] for it in page2["items"]}
    assert ids1.isdisjoint(ids2)
