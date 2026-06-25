from sqlalchemy.dialects import postgresql, sqlite

from app.db import JSONB_OR_JSON, make_engine


def test_json_variant_compiles_per_dialect():
    assert JSONB_OR_JSON.compile(dialect=postgresql.dialect()) == "JSONB"
    assert JSONB_OR_JSON.compile(dialect=sqlite.dialect()) == "JSON"


def test_make_engine_routes_dialect():
    assert make_engine("sqlite://").dialect.name == "sqlite"
    assert make_engine("postgresql+psycopg://u:p@h:5432/db").dialect.name == "postgresql"


def test_make_engine_postgres_sets_pre_ping():
    eng = make_engine("postgresql+psycopg://u:p@h:5432/db")
    assert eng.pool._pre_ping is True
