from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
_EXPECTED = {
    "series", "episode", "line", "scene", "vocab", "grammar_point",
    "daily_session", "app_setting", "tower_progress", "player_stats",
    "alembic_version",
}


def _cfg(db_path: Path) -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_upgrade_head_creates_all_tables(tmp_path):
    db = tmp_path / "m.db"
    command.upgrade(_cfg(db), "head")
    insp = inspect(create_engine(f"sqlite:///{db}"))
    assert _EXPECTED <= set(insp.get_table_names())


def test_downgrade_base_drops_tables(tmp_path):
    db = tmp_path / "m.db"
    cfg = _cfg(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    insp = inspect(create_engine(f"sqlite:///{db}"))
    assert "vocab" not in set(insp.get_table_names())


def test_pg_trgm_migration_is_noop_on_sqlite(tmp_path):
    db = tmp_path / "m.db"
    cfg = _cfg(db)
    command.upgrade(cfg, "head")        # 含 0002,sqlite 下应 no-op 不报错
    command.downgrade(cfg, "0001_initial")
    insp = inspect(create_engine(f"sqlite:///{db}"))
    assert "vocab" in set(insp.get_table_names())   # 表仍在(只回退索引迁移)
