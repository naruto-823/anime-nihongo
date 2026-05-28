from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite:///"):
        db_path = Path(url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """建表。导入 models 以注册到 Base.metadata。"""
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)


from app.config import settings  # noqa: E402

_engine = make_engine(settings.database_url)
SessionLocal = make_session_factory(_engine)


def _add_column_if_missing(engine: Engine, table: str, column: str, ddl: str) -> None:
    """幂等加列。SQLite 没 IF NOT EXISTS 的 ADD COLUMN，靠捕错来识别。"""
    try:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "duplicate column" in msg or "already exists" in msg:
            return
        raise


def _migrate_in_place(engine: Engine) -> None:
    """补齐 create_all 不会处理的新增列。每次启动跑一次。"""
    _add_column_if_missing(engine, "series", "anilist_id", "INTEGER")
    _add_column_if_missing(engine, "series", "anilist_status",
                           "VARCHAR DEFAULT 'pending'")
    _add_column_if_missing(engine, "series", "characters", "JSON")
    _add_column_if_missing(engine, "episode", "scenes_split",
                           "BOOLEAN DEFAULT 0")


def init_app_db() -> None:
    """应用启动时建表 + 补列。"""
    init_db(_engine)
    _migrate_in_place(_engine)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
