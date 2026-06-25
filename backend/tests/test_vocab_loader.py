from app.models import Vocab
from app.vocab_loader import load_vocab_seed


def test_loads_seed(db_session):
    n = load_vocab_seed(db_session)
    assert n >= 5000
    v = db_session.query(Vocab).filter_by(headword="高校").one()
    assert v.reading == "こうこう"
    assert "高中" in v.meaning_zh
    assert v.jlpt_level == "N5"


def test_all_levels_present(db_session):
    load_vocab_seed(db_session)
    levels = {lv for (lv,) in db_session.query(Vocab.jlpt_level).distinct()}
    assert {"N1", "N2", "N3", "N4", "N5"} <= levels


def test_loader_is_idempotent(db_session):
    load_vocab_seed(db_session)
    first = db_session.query(Vocab).count()
    load_vocab_seed(db_session)
    assert db_session.query(Vocab).count() == first
