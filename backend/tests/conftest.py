import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import get_db, init_db, make_session_factory
from app.main import app


class _NoCloseSession:
    """把 db_session 包一层：close() 是 no-op，避免 BackgroundTasks 关掉夹具会话。"""

    def __init__(self, session):
        self._s = session

    def __getattr__(self, name):
        return getattr(self._s, name)

    def close(self):
        pass


@pytest.fixture
def db_session():
    # StaticPool ensures all threads share the same in-memory connection,
    # which is required for TestClient (runs route handlers in worker threads).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session, monkeypatch):
    """TestClient，get_db 与 SessionLocal 都覆盖为测试用的内存会话。

    刻意不使用 `with TestClient(...)`：不触发 startup/shutdown 生命周期事件，
    避免 startup 里的 init_app_db / load_grammar_seed 操作真实文件库。
    测试库由 db_session 夹具建表；需要语法种子的测试自行调用 load_grammar_seed。
    BackgroundTasks 用的 SessionLocal 也指向同一 db_session，使后台写入在测试内可见。
    """
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr("app.api.series.SessionLocal",
                        lambda: _NoCloseSession(db_session))
    yield TestClient(app)
    app.dependency_overrides.clear()
