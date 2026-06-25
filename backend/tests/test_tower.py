import random
from datetime import date

import pytest

from app.models import GrammarPoint, TowerProgress, Vocab
from app.services import tower
from app.services.tower import LockedStageError


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


def test_stars_for_thresholds():
    assert tower.stars_for(1.0) == 3
    assert tower.stars_for(0.8) == 2
    assert tower.stars_for(0.6) == 1
    assert tower.stars_for(0.59) == 0


def test_build_quiz_stage_has_questions(db_session):
    _seed_level(db_session, n_vocab=20, n_gram=6)
    qs = tower.build_quiz(db_session, "N5", 0, 0, False, random.Random(1))
    assert len(qs) == 10                       # 8 词 + 2 语法
    assert all(q["answer"] in q["options"] for q in qs)
    assert {q["item"]["kind"] for q in qs} == {"vocab", "grammar"}


def test_build_quiz_boss_is_bigger(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20)
    qs = tower.build_quiz(db_session, "N5", 0, 0, True, random.Random(1))
    assert len(qs) >= 15


def test_submit_updates_progress_xp_and_srs(db_session):
    v = Vocab(headword="飲む", reading="のむ", meaning_zh="喝", pos="他動1",
              jlpt_level="N5", source_line_id=None)
    g = GrammarPoint(key="N5-g0", name="〜て", jlpt_level="N5",
                     explanation="表示", curated=True)
    db_session.add_all([v, g])
    db_session.commit()

    results = [
        {"item": {"kind": "vocab", "id": v.id}, "correct": True},
        {"item": {"kind": "grammar", "id": g.id}, "correct": False},
    ]
    out = tower.submit_result(db_session, "N5", 0, 0, False, results, today=date(2026, 6, 25))

    assert out["accuracy"] == 0.5
    assert out["stars"] == 0 and out["passed"] is False
    assert out["xp_gained"] == 10            # 1 对 × 10
    # 进度落库
    tp = db_session.query(TowerProgress).filter_by(level="N5", zone_idx=0,
                                                   stage_idx=0, is_boss=False).one()
    assert tp.attempts == 1 and tp.best_accuracy == 0.5
    # SRS:都入池;答错的语法 due=今天且 learning
    assert db_session.get(Vocab, v.id).in_srs is True
    gg = db_session.get(GrammarPoint, g.id)
    assert gg.in_srs is True and gg.status == "learning"
    assert gg.due_date == date(2026, 6, 25)


def test_submit_keeps_best_and_anime_bonus(db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", pos="名",
              jlpt_level="N5", source_line_id=999)        # 番剧词
    db_session.add(v)
    db_session.commit()
    results = [{"item": {"kind": "vocab", "id": v.id}, "correct": True}]
    out = tower.submit_result(db_session, "N5", 0, 0, False, results, today=date(2026, 6, 25))
    assert out["xp_gained"] == 15            # 10 × 1.5 番剧加成
    assert out["stars"] == 3 and out["passed"] is True
    # 再交一次更差成绩,best 不应下降
    tower.submit_result(db_session, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab", "id": v.id}, "correct": False}],
                        today=date(2026, 6, 25))
    tp = db_session.query(TowerProgress).filter_by(level="N5", zone_idx=0,
                                                   stage_idx=0, is_boss=False).one()
    assert tp.stars == 3 and tp.best_accuracy == 1.0 and tp.attempts == 2


def test_tower_map_initial_locks(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20, level="N5")   # 1 区 5 关 + Boss
    m = tower.tower_map(db_session)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["unlocked"] is True
    stage0 = n5["zones"][0]["stages"][0]
    assert stage0["unlocked"] is True and stage0["stage_idx"] == 0
    stage1 = n5["zones"][0]["stages"][1]
    assert stage1["unlocked"] is False           # 未过第 0 关
    n4 = next(lv for lv in m["levels"] if lv["level"] == "N4")
    assert n4["unlocked"] is False


def test_tower_map_unlocks_next_after_clear(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20, level="N5")
    tower.submit_result(db_session, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab",
                          "id": db_session.query(Vocab).first().id}, "correct": True}])
    m = tower.tower_map(db_session)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["zones"][0]["stages"][1]["unlocked"] is True     # 第 1 关解锁


# ── 修复 1: submit_result 校验关卡已解锁 ────────────────────────────────────

def test_submit_rejects_locked_stage(db_session):
    """zone0 stage0 默认解锁; stage1 未过 stage0 时应拒绝。"""
    _seed_level(db_session, n_vocab=20, n_gram=6, level="N5")
    vid = db_session.query(Vocab).first().id
    results = [{"item": {"kind": "vocab", "id": vid}, "correct": True}]

    # stage1 未解锁 -> 应抛 LockedStageError
    with pytest.raises(LockedStageError):
        tower.submit_result(db_session, "N5", 0, 1, False, results)

    # 数据库无 TowerProgress 记录
    count = db_session.query(TowerProgress).count()
    assert count == 0

    # 玩家 XP 仍为 0
    from app.models import PlayerStats
    p = db_session.get(PlayerStats, 1)
    assert p is None or p.total_xp == 0


def test_submit_unlocked_stage0_still_passes(db_session):
    """stage0 (N5 zone0) 默认解锁,不应抛异常。"""
    _seed_level(db_session, n_vocab=20, n_gram=6, level="N5")
    vid = db_session.query(Vocab).first().id
    results = [{"item": {"kind": "vocab", "id": vid}, "correct": True}]
    out = tower.submit_result(db_session, "N5", 0, 0, False, results)
    assert out["passed"] is True
