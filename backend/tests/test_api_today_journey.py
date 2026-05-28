from app.models import Episode, Line, Scene, Series


def test_journey_no_series(client, db_session):
    body = client.get("/api/today/journey").json()
    assert body["series"] is None
    assert body["current_episode"] is None
    assert body["scenes"] == []
    assert body["streak"] == 0
    assert body["due_total"] == 0


def test_journey_series_no_episode(client, db_session):
    s = Series(title="番", is_current=True); db_session.add(s); db_session.commit()
    body = client.get("/api/today/journey").json()
    assert body["series"]["id"] == s.id
    assert body["series"]["main_character"] is not None
    # 没 character → main_character 仍非 null，但 name/image 为 null，fallback_initial 取 series.title 首字符
    assert body["series"]["main_character"]["fallback_initial"] == "番"
    assert body["current_episode"] is None


def test_journey_full_flow_with_main_character(client, db_session):
    s = Series(title="孤独摇滚", is_current=True, anilist_status="matched",
               anilist_id=130003,
               characters=[
                   {"name_en": "Hitori", "name_jp": "後藤ひとり",
                    "image_url": "https://x/h.png", "role": "MAIN"},
                   {"name_en": "Niko", "name_jp": "伊地知虹夏",
                    "image_url": "https://x/n.png", "role": "SUPPORTING"},
               ])
    db_session.add(s); db_session.commit()
    ep = Episode(series_id=s.id, number=5, source="upload", status="ready",
                 total_lines=30, read_position=15, scenes_split=True)
    for i in range(30):
        ep.lines.append(Line(idx=i, text_jp=f"行{i}", processed=True))
    db_session.add(ep); db_session.commit()
    db_session.add_all([
        Scene(episode_id=ep.id, idx=0, title_zh="A",
              start_line_idx=0, end_line_idx=9, line_count=10),
        Scene(episode_id=ep.id, idx=1, title_zh="B",
              start_line_idx=10, end_line_idx=19, line_count=10),
        Scene(episode_id=ep.id, idx=2, title_zh="C",
              start_line_idx=20, end_line_idx=29, line_count=10),
    ])
    db_session.commit()

    body = client.get("/api/today/journey").json()
    assert body["series"]["main_character"]["name_jp"] == "後藤ひとり"
    assert body["series"]["main_character"]["image_url"] == "https://x/h.png"
    assert body["series"]["main_character"]["fallback_initial"] == "後"
    assert body["current_episode"]["id"] == ep.id
    assert body["current_episode"]["completed_scenes"] == 1
    assert body["current_episode"]["total_scenes"] == 3
    assert [s["state"] for s in body["scenes"]] == ["done", "current", "locked"]


def test_journey_main_character_fallback_initial_from_series_title(
        client, db_session):
    s = Series(title="孤独摇滚", is_current=True, anilist_status="not_found")
    db_session.add(s); db_session.commit()
    body = client.get("/api/today/journey").json()
    mc = body["series"]["main_character"]
    assert mc is not None
    assert mc["name_jp"] is None
    assert mc["name_en"] is None
    assert mc["image_url"] is None
    assert mc["fallback_initial"] == "孤"


def test_journey_main_character_picks_first_with_image(client, db_session):
    s = Series(title="A", is_current=True, anilist_status="matched",
               characters=[
                   {"name_en": "NoImg", "name_jp": "無画",
                    "image_url": None, "role": "MAIN"},
                   {"name_en": "Has", "name_jp": "画あり",
                    "image_url": "https://x/h.png", "role": "SUPPORTING"},
               ])
    db_session.add(s); db_session.commit()
    mc = client.get("/api/today/journey").json()["series"]["main_character"]
    assert mc["name_jp"] == "画あり"
    assert mc["image_url"] == "https://x/h.png"
