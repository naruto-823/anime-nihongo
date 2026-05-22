from sqlalchemy import inspect

from app.db import init_db, make_engine, make_session_factory


def test_make_engine_and_session():
    engine = make_engine("sqlite://")
    session_factory = make_session_factory(engine)
    init_db(engine)
    with session_factory() as session:
        assert session.is_active


def test_init_db_is_idempotent():
    engine = make_engine("sqlite://")
    init_db(engine)
    init_db(engine)  # 第二次不应报错
    assert inspect(engine) is not None
