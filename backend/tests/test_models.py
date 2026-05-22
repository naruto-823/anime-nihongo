import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Episode, GrammarPoint, Line, Series, Vocab


def test_series_episode_line_chain(db_session):
    series = Series(title="测试番", title_jp="テスト")
    episode = Episode(series=series, number=1, source="upload", status="processing")
    line = Line(episode=episode, idx=0, text_jp="これはテストだ", processed=False)
    db_session.add(series)
    db_session.commit()
    assert line.id is not None
    assert episode.series.title == "测试番"
    assert series.episodes[0].lines[0].text_jp == "これはテストだ"


def test_vocab_unique_headword_reading(db_session):
    db_session.add(Vocab(headword="本", reading="ほん", meaning_zh="书"))
    db_session.commit()
    db_session.add(Vocab(headword="本", reading="ほん", meaning_zh="重复"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_grammar_point_defaults(db_session):
    gp = GrammarPoint(key="ni-atatte", name="〜にあたって", jlpt_level="N2",
                      explanation="在…之际", curated=True)
    db_session.add(gp)
    db_session.commit()
    assert gp.status == "locked"
    assert gp.in_srs is False
    assert gp.ease == 2.5
