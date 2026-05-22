from pathlib import Path

from app.cli import import_episode_from_file
from app.models import Line, Series
from app.services import pipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_from_file_then_process(db_session, monkeypatch):
    from app.grammar_loader import load_grammar_seed
    from tests.test_pipeline import _fake_llm

    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)

    episode = import_episode_from_file(
        db_session, series_title="测试番", number=1,
        file_path=str(FIXTURES / "sample.srt"))

    assert db_session.query(Series).filter_by(title="测试番").count() == 1
    lines = db_session.query(Line).filter_by(episode_id=episode.id).all()
    assert len(lines) == 2

    pipeline.process_episode(db_session, episode.id)
    db_session.refresh(episode)
    assert episode.status == "ready"
    assert all(ln.processed for ln in lines)
