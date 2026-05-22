from app.grammar_loader import load_grammar_seed
from app.models import GrammarPoint


def test_loads_seed(db_session):
    n = load_grammar_seed(db_session)
    assert n >= 150
    gp = db_session.query(GrammarPoint).filter_by(key="ni-atatte").one()
    assert gp.name == "〜にあたって"
    assert gp.curated is True
    assert gp.status == "locked"


def test_loader_is_idempotent(db_session):
    load_grammar_seed(db_session)
    first = db_session.query(GrammarPoint).count()
    load_grammar_seed(db_session)
    assert db_session.query(GrammarPoint).count() == first
