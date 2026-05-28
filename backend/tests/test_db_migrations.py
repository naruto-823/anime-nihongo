from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.db import _migrate_in_place


def _engine_with_old_series_table():
    """模拟"旧库"：没有新加列的 series 表。"""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE series (id INTEGER PRIMARY KEY, title VARCHAR)"
        ))
        conn.execute(text(
            "CREATE TABLE episode (id INTEGER PRIMARY KEY, total_lines INTEGER)"
        ))
    return engine


def _columns(engine, table):
    with engine.begin() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def test_migrate_adds_missing_columns():
    engine = _engine_with_old_series_table()
    _migrate_in_place(engine)
    assert {"anilist_id", "anilist_status", "characters"} <= _columns(engine, "series")
    assert "scenes_split" in _columns(engine, "episode")


def test_migrate_is_idempotent():
    engine = _engine_with_old_series_table()
    _migrate_in_place(engine)
    _migrate_in_place(engine)  # 第二次不应抛错
    assert {"anilist_id", "anilist_status", "characters"} <= _columns(engine, "series")
