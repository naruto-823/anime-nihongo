from pathlib import Path

from sqlalchemy import Engine, create_engine
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
