import random

from app.models import GrammarPoint, Vocab
from app.services import tower


def _seed_level(db, n_vocab=20, n_gram=6, level="N5"):
    for i in range(n_vocab):
        db.add(Vocab(headword=f"語{i}", reading=f"よ{i}", meaning_zh=f"义{i}",
                     pos="名", jlpt_level=level))
    for i in range(n_gram):
        db.add(GrammarPoint(key=f"{level}-g{i}", name=f"〜文法{i}",
                            jlpt_level=level, explanation=f"含义{i}", curated=True))
    db.commit()


def test_stage_slice_sizes(db_session):
    _seed_level(db_session, n_vocab=20, n_gram=6)
    v, g = tower.stage_items(db_session, "N5", 0, 0)
    assert [x.headword for x in v] == [f"語{i}" for i in range(8)]
    assert [x.name for x in g] == ["〜文法0", "〜文法1"]
    v2, _ = tower.stage_items(db_session, "N5", 0, 1)
    assert [x.headword for x in v2] == [f"語{i}" for i in range(8, 16)]


def test_zone_items_unions_five_stages(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20)
    v, g = tower.zone_items(db_session, "N5", 0)
    assert len(v) == 40 and len(g) == 10        # 5 关 × (8 词 + 2 语法)
