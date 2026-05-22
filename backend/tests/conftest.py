import pytest

from app.db import init_db, make_engine, make_session_factory


@pytest.fixture
def db_session():
    engine = make_engine("sqlite://")
    init_db(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()
