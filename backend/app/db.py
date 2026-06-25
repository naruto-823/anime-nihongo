from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import JSON, Engine, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# JSON 列:生产(postgres)用 JSONB,其余(测试 sqlite)用 JSON
JSONB_OR_JSON = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if url.startswith("sqlite:///"):
            db_path = Path(url.removeprefix("sqlite:///"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args=connect_args)
    # PostgreSQL 等生产库:连接池 + 预检
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """建表。导入 models 以注册到 Base.metadata。"""
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)


from app.config import settings  # noqa: E402

_engine = make_engine(settings.database_url)
SessionLocal = make_session_factory(_engine)


def init_app_db() -> None:
    """应用启动时准备 schema。

    sqlite(本地/测试便利):直接 create_all。
    postgres(生产):schema 由 `alembic upgrade head`(容器 entrypoint)管理,此处不建表。
    """
    if _engine.dialect.name == "sqlite":
        init_db(_engine)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖:每请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
