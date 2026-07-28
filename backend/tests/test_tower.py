import random
from datetime import date

import pytest

from app.models import GrammarPoint, TowerProgress, Vocab
from app.services import tower
from app.services.tower import LockedStageError


def _seed_level(db, n_vocab=20, n_gram=6, level="N5"):
    prefix = level  # headword 前缀防止跨层冲突
    for i in range(n_vocab):
        db.add(Vocab(headword=f"{prefix}語{i}", reading=f"{prefix}よ{i}",
                     meaning_zh=f"义{level}{i}", pos="名", jlpt_level=level))
    for i in range(n_gram):
        db.add(GrammarPoint(key=f"{level}-g{i}", name=f"〜文法{level}{i}",
                            jlpt_level=level, explanation=f"含义{level}{i}", curated=True))
    db.commit()


def test_stage_slice_sizes(db_session):
    _seed_level(db_session, n_vocab=20, n_gram=6)
    v, g = tower.stage_items(db_session, "N5", 0, 0)
    assert [x.headword for x in v] == [f"N5語{i}" for i in range(8)]
    assert [x.name for x in g] == ["〜文法N50", "〜文法N51"]
    v2, _ = tower.stage_items(db_session, "N5", 0, 1)
    assert [x.headword for x in v2] == [f"N5語{i}" for i in range(8, 16)]


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
    # SRS 状态按用户隔离，不修改公共题库
    from app.models import UserGrammarProgress, UserVocabProgress
    vp = db_session.query(UserVocabProgress).filter_by(user_id=1, vocab_id=v.id).one()
    gp = db_session.query(UserGrammarProgress).filter_by(user_id=1, grammar_id=g.id).one()
    assert vp.in_srs is True
    assert gp.in_srs is True and gp.status == "learning"
    assert gp.due_date == date(2026, 6, 25)


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


# ── 修复 2: 跨层解锁稳健性(C1) ──────────────────────────────────────────────

def _pass_stage(db_session, level, zone_idx, stage_idx, is_boss=False):
    """辅助:用 vocab id=1 的结果让该关通过(accuracy=1.0)。"""
    vocab = db_session.query(Vocab).filter_by(jlpt_level=level).first()
    results = [{"item": {"kind": "vocab", "id": vocab.id}, "correct": True}]
    tower.submit_result(db_session, level, zone_idx, stage_idx, is_boss, results)


def test_tower_map_multizone_level_unlock(db_session):
    """≥2 区的层: 仅当所有区 Boss 都 cleared 后下一层才解锁。
    80 词 → num_stages=10 → num_zones=2(zone0:5关+Boss, zone1:5关+Boss)
    """
    _seed_level(db_session, n_vocab=80, n_gram=20, level="N5")
    _seed_level(db_session, n_vocab=8, n_gram=2, level="N4")

    # 通过 zone0 的全部5小关
    for s in range(5):
        _pass_stage(db_session, "N5", 0, s, False)

    # 通过 zone0 Boss
    _pass_stage(db_session, "N5", 0, 0, True)

    # 此时 zone1 的 stage0 应解锁,但 N4 仍应锁定
    m = tower.tower_map(db_session)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["zones"][1]["stages"][0]["unlocked"] is True

    n4 = next(lv for lv in m["levels"] if lv["level"] == "N4")
    assert n4["unlocked"] is False, "仅 zone0 Boss 通过,N4 仍应锁定"

    # 通过 zone1 全部5小关 + Boss
    for s in range(5):
        _pass_stage(db_session, "N5", 1, s, False)
    _pass_stage(db_session, "N5", 1, 0, True)

    m2 = tower.tower_map(db_session)
    n4_2 = next(lv for lv in m2["levels"] if lv["level"] == "N4")
    assert n4_2["unlocked"] is True, "zone0+zone1 Boss 均 cleared,N4 应解锁"


# ── 修复 5: best_accuracy 用严格大于(I4) ────────────────────────────────────

def test_best_accuracy_strict_greater_equal_does_not_overwrite(db_session):
    """等分(accuracy == best_accuracy)时不应重写 stars。"""
    _seed_level(db_session, n_vocab=8, n_gram=0, level="N5")
    vid = db_session.query(Vocab).first().id

    # 第一次提交 1/1 = 100% accuracy, 3 stars
    out1 = tower.submit_result(db_session, "N5", 0, 0, False,
                               [{"item": {"kind": "vocab", "id": vid}, "correct": True}])
    assert out1["stars"] == 3

    tp = db_session.query(TowerProgress).filter_by(level="N5", zone_idx=0,
                                                   stage_idx=0, is_boss=False).one()
    assert tp.stars == 3 and tp.best_accuracy == 1.0

    # 手动将 stars 改为某个值,模拟「等分不应覆盖」的场景
    # 实际上 3 stars == 3 stars 不能区分;改为先提交 3 stars,再降 stars=1 后提交同分
    # 直接测: 提交与 best 相同 accuracy 时,stars 不变
    tp.stars = 1  # 手动修改 stars 为 1(模拟数据)
    db_session.commit()

    # 再次提交相同 accuracy(1/1=100%)——等分,严格大于时不更新,stars 应保持为 1
    tower.submit_result(db_session, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab", "id": vid}, "correct": True}])
    db_session.refresh(tp)
    assert tp.stars == 1, "等分时 stars 不应被覆盖(严格大于才更新)"
    assert tp.best_accuracy == 1.0


# ── 修复 3: 语法番剧加成且状态判定不被自身改写污染(I5) ──────────────────────

def test_grammar_anime_bonus_uses_original_status(db_session):
    """语法番剧加成:原始 status=seen → xp=15;原始 status=locked → xp=10。
    且加成判定在 status 被改为 learning 之前捕获原始值。
    """
    from app.models import GrammarPoint as GP
    _seed_level(db_session, n_vocab=8, n_gram=0, level="N5")

    # status=seen 的语法点 → 应享番剧加成
    g_seen = GP(key="N5-seen", name="〜て(seen)", jlpt_level="N5",
                explanation="连接", curated=True, status="seen")
    # status=locked 的语法点 → 不享番剧加成
    g_locked = GP(key="N5-locked", name="〜で(locked)", jlpt_level="N5",
                  explanation="工具", curated=True, status="locked")
    db_session.add_all([g_seen, g_locked])
    db_session.commit()

    results = [
        {"item": {"kind": "grammar", "id": g_seen.id}, "correct": True},
        {"item": {"kind": "grammar", "id": g_locked.id}, "correct": True},
    ]
    out = tower.submit_result(db_session, "N5", 0, 0, False, results)

    # seen → 15 XP; locked → 10 XP; 合计 25
    assert out["xp_gained"] == 25, f"期望 25 XP,实际 {out['xp_gained']}"

    # 公共题库保持不变；用户学习状态独立变为 learning
    db_session.refresh(g_seen)
    db_session.refresh(g_locked)
    assert g_seen.status == "seen"
    assert g_locked.status == "locked"
    from app.models import UserGrammarProgress
    rows = db_session.query(UserGrammarProgress).filter_by(user_id=1).all()
    assert len(rows) == 2 and all(row.status == "learning" for row in rows)
