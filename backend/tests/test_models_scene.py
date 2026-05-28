import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Episode, Scene, Series


def _episode(db_session):
    s = Series(title="番")
    e = Episode(series=s, number=1, source="upload", status="ready",
                total_lines=100)
    db_session.add(s)
    db_session.commit()
    return e


def test_scene_create_with_required_fields(db_session):
    ep = _episode(db_session)
    sc = Scene(episode_id=ep.id, idx=0, title_zh="便利店发抖",
               start_line_idx=0, end_line_idx=22, line_count=23)
    db_session.add(sc)
    db_session.commit()
    assert sc.id is not None


def test_scene_unique_per_episode_idx(db_session):
    ep = _episode(db_session)
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="A",
                         start_line_idx=0, end_line_idx=10, line_count=11))
    db_session.commit()
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="B",
                         start_line_idx=11, end_line_idx=20, line_count=10))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_scene_cascade_delete_with_episode(db_session):
    ep = _episode(db_session)
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="X",
                         start_line_idx=0, end_line_idx=5, line_count=6))
    db_session.commit()
    db_session.delete(ep)
    db_session.commit()
    assert db_session.query(Scene).count() == 0


def test_series_has_anilist_fields_with_defaults(db_session):
    s = Series(title="孤独摇滚")
    db_session.add(s)
    db_session.commit()
    assert s.anilist_id is None
    assert s.anilist_status == "pending"
    assert s.characters is None


def test_series_characters_json_roundtrip(db_session):
    s = Series(title="A")
    s.characters = [{"name_en": "Hitori Gotoh", "name_jp": "後藤ひとり",
                     "image_url": "https://example/h.png", "role": "MAIN"}]
    s.anilist_id = 130003
    s.anilist_status = "matched"
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    assert s.characters[0]["name_jp"] == "後藤ひとり"
    assert s.anilist_id == 130003


def test_episode_scenes_split_default_false(db_session):
    s = Series(title="番")
    e = Episode(series=s, number=1, source="upload", status="processing",
                total_lines=10)
    db_session.add(s)
    db_session.commit()
    assert e.scenes_split is False
