from math import ceil

from sqlalchemy import select

from app.models import GrammarPoint, Vocab

LEVELS = ["N5", "N4", "N3", "N2", "N1"]
STAGE_VOCAB = 8
STAGE_GRAMMAR = 2
STAGES_PER_ZONE = 5


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
