from datetime import date as _date
from math import ceil

from sqlalchemy import select

from app.models import GrammarPoint, PlayerStats, TowerProgress, Vocab
from app.services.quiz_bank import make_grammar_question, make_vocab_question

LEVELS = ["N5", "N4", "N3", "N2", "N1"]
STAGE_VOCAB = 8
STAGE_GRAMMAR = 2
STAGES_PER_ZONE = 5


class LockedStageError(Exception):
    """目标关卡未解锁,拒绝提交。"""


def level_items(db, level):
    vocab = db.scalars(
        select(Vocab).where(Vocab.jlpt_level == level).order_by(Vocab.id)
    ).all()
    grammar = db.scalars(
        select(GrammarPoint).where(GrammarPoint.jlpt_level == level).order_by(GrammarPoint.id)
    ).all()
    return list(vocab), list(grammar)


def num_stages(vocab_count: int) -> int:
    return max(1, ceil(vocab_count / STAGE_VOCAB))


def num_zones(stage_count: int) -> int:
    return max(1, ceil(stage_count / STAGES_PER_ZONE))


def _global_stage(zone_idx: int, stage_idx: int) -> int:
    return zone_idx * STAGES_PER_ZONE + stage_idx


def stage_items(db, level, zone_idx, stage_idx):
    vocab, grammar = level_items(db, level)
    g = _global_stage(zone_idx, stage_idx)
    v_slice = vocab[g * STAGE_VOCAB:(g + 1) * STAGE_VOCAB]
    g_slice = grammar[g * STAGE_GRAMMAR:(g + 1) * STAGE_GRAMMAR]
    return v_slice, g_slice


def zone_items(db, level, zone_idx):
    vs, gs = [], []
    for s in range(STAGES_PER_ZONE):
        v, g = stage_items(db, level, zone_idx, s)
        vs.extend(v)
        gs.extend(g)
    return vs, gs


BOSS_MAX_Q = 20


def stars_for(accuracy: float) -> int:
    if accuracy >= 1.0:
        return 3
    if accuracy >= 0.8:
        return 2
    if accuracy >= 0.6:
        return 1
    return 0


BOSS_PASS = 0.8
STAGE_PASS = 0.6
XP_PER_CORRECT = 10


def _is_cleared(idx, level, zone_idx, stage_idx, is_boss):
    tp = idx.get((level, zone_idx, stage_idx, is_boss))
    return bool(tp and tp.cleared)


def is_cell_unlocked(db, level, zone_idx, stage_idx, is_boss, user_id=1) -> bool:
    """判断给定关卡是否已解锁。规则与 tower_map 完全一致。"""
    idx = _progress_index(db, user_id)

    # N5 及各层第0区第0关默认解锁
    level_idx = LEVELS.index(level) if level in LEVELS else -1
    if level_idx < 0:
        return False

    # 层解锁:N5 始终解锁;否则上一层所有区 Boss 全 cleared
    if level_idx == 0:
        level_unlocked = True
    else:
        prev_level = LEVELS[level_idx - 1]
        prev_vocab, _ = level_items(db, prev_level)
        prev_stage_count = num_stages(len(prev_vocab))
        prev_zone_count = num_zones(prev_stage_count)
        level_unlocked = all(
            _is_cleared(idx, prev_level, z, 0, True)
            for z in range(prev_zone_count)
        )

    if not level_unlocked:
        return False

    # 区解锁:第0区 Boss 只要层解锁即可;后续区需上一区 Boss cleared
    if zone_idx == 0:
        zone_unlocked = True
    else:
        zone_unlocked = _is_cleared(idx, level, zone_idx - 1, 0, True)

    if not zone_unlocked:
        return False

    if is_boss:
        # Boss 解锁:该区5个小关全 cleared
        return all(
            _is_cleared(idx, level, zone_idx, s, False)
            for s in range(STAGES_PER_ZONE)
        )
    else:
        # 小关解锁:第0关直接解锁;后续关需上一关 cleared
        if stage_idx == 0:
            return True
        return _is_cleared(idx, level, zone_idx, stage_idx - 1, False)


def _get_or_create_progress(db, level, zone_idx, stage_idx, is_boss, user_id=1):
    tp = db.query(TowerProgress).filter_by(
        user_id=user_id, level=level, zone_idx=zone_idx,
        stage_idx=stage_idx, is_boss=is_boss).one_or_none()
    if tp is None:
        tp = TowerProgress(user_id=user_id, level=level, zone_idx=zone_idx, stage_idx=stage_idx,
                           is_boss=is_boss, cleared=False, stars=0,
                           best_accuracy=0.0, attempts=0)
        db.add(tp)
    return tp


def _player(db, user_id=1):
    p = db.get(PlayerStats, user_id)
    if p is None:
        p = PlayerStats(id=user_id, total_xp=0, player_level=1)
        db.add(p)
    return p


def submit_result(db, level, zone_idx, stage_idx, is_boss, results, today=None, user_id=1):
    if not is_cell_unlocked(db, level, zone_idx, stage_idx, is_boss, user_id):
        raise LockedStageError(f"关卡未解锁: {level} zone{zone_idx} stage{stage_idx} boss={is_boss}")
    today = today or _date.today()
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total if total else 0.0
    stars = stars_for(accuracy)
    passed = accuracy >= (BOSS_PASS if is_boss else STAGE_PASS)

    xp_gained = 0
    for r in results:
        kind, iid = r["item"]["kind"], r["item"]["id"]
        model = Vocab if kind == "vocab" else GrammarPoint
        obj = db.get(model, iid)
        if obj is None:
            continue
        obj.in_srs = True
        # 在修改 status 之前先捕获原始状态,用于番剧加成判定
        original_grammar_status = getattr(obj, "status", None) if kind == "grammar" else None
        if kind == "grammar":
            obj.status = "learning"
        if not r["correct"]:
            obj.due_date = today
        elif obj.due_date is None:
            obj.due_date = today
        if r["correct"]:
            if kind == "vocab":
                anime = getattr(obj, "source_line_id", None) is not None
            else:
                # 语法加成条件: 原始 status in {"seen", "learning"}
                anime = original_grammar_status in {"seen", "learning"}
            xp_gained += round(XP_PER_CORRECT * (1.5 if anime else 1))

    tp = _get_or_create_progress(db, level, zone_idx, stage_idx, is_boss, user_id)
    tp.attempts += 1
    if accuracy > tp.best_accuracy:
        tp.best_accuracy = accuracy
        tp.stars = stars
    if passed:
        tp.cleared = True

    player = _player(db, user_id)
    player.total_xp += xp_gained
    player.player_level = 1 + player.total_xp // 500     # 每 500 XP 升 1 级

    db.commit()
    return {"stars": stars, "accuracy": accuracy, "passed": passed,
            "xp_gained": xp_gained, "total_xp": player.total_xp}


def _progress_index(db, user_id=1):
    idx = {}
    for tp in db.query(TowerProgress).filter_by(user_id=user_id).all():
        idx[(tp.level, tp.zone_idx, tp.stage_idx, tp.is_boss)] = tp
    return idx


def tower_map(db, user_id=1):
    idx = _progress_index(db, user_id)

    def cell(level, zone, stage, is_boss, unlocked):
        tp = idx.get((level, zone, stage, is_boss))
        return {"stage_idx": stage, "is_boss": is_boss, "unlocked": unlocked,
                "cleared": bool(tp and tp.cleared), "stars": (tp.stars if tp else 0)}

    def cleared(level, zone, stage, is_boss):
        tp = idx.get((level, zone, stage, is_boss))
        return bool(tp and tp.cleared)

    levels_out = []
    prev_level_done = True
    for level in LEVELS:
        vocab, _ = level_items(db, level)
        stage_count = num_stages(len(vocab))
        zone_count = num_zones(stage_count)
        level_unlocked = prev_level_done
        zones_out = []
        prev_zone_boss_done = True
        for z in range(zone_count):
            zone_unlocked = level_unlocked and prev_zone_boss_done
            stages_out = []
            prev_stage_done = True
            for s in range(STAGES_PER_ZONE):
                unlocked = zone_unlocked and prev_stage_done
                stages_out.append(cell(level, z, s, False, unlocked))
                prev_stage_done = cleared(level, z, s, False)
            all_stages_done = all(cleared(level, z, s, False)
                                  for s in range(STAGES_PER_ZONE))
            boss_unlocked = zone_unlocked and all_stages_done
            stages_out.append(cell(level, z, 0, True, boss_unlocked))
            zones_out.append({"zone_idx": z, "stages": stages_out})
            prev_zone_boss_done = cleared(level, z, 0, True)
        levels_out.append({"level": level, "unlocked": level_unlocked,
                           "zones": zones_out})
        # 整层完成 = 该层所有区的 Boss 均 cleared
        prev_level_done = all(cleared(level, z, 0, True) for z in range(zone_count))
    return {"levels": levels_out}


def build_quiz(db, level, zone_idx, stage_idx, is_boss, rng):
    vocab_pool, grammar_pool = level_items(db, level)
    if is_boss:
        vs, gs = zone_items(db, level, zone_idx)
    else:
        vs, gs = stage_items(db, level, zone_idx, stage_idx)
    questions = []
    for v in vs:
        questions.append(make_vocab_question(v, vocab_pool, rng))
    for g in gs:
        questions.append(make_grammar_question(g, grammar_pool, rng))
    rng.shuffle(questions)
    if is_boss:
        questions = questions[:BOSS_MAX_Q]
    return questions
