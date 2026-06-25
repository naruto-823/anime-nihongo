import random

from app.services.quiz_bank import vocab_meaning_q, vocab_reading_q


class V:
    def __init__(self, id, headword, reading, meaning_zh, pos="名", source_line_id=None):
        self.id = id; self.headword = headword; self.reading = reading
        self.meaning_zh = meaning_zh; self.pos = pos; self.source_line_id = source_line_id


def _pool():
    return [V(i, f"词{i}", f"よみ{i}", f"释义{i}") for i in range(1, 8)]


def test_vocab_meaning_q_basic():
    target = V(1, "高校", "こうこう", "高中")
    rng = random.Random(0)
    q = vocab_meaning_q(target, _pool() + [target], rng)
    assert q["type"] == "meaning"
    assert q["prompt"] == "高校（こうこう）"
    assert q["answer"] == "高中"
    assert q["answer"] in q["options"]
    assert len(q["options"]) == 4
    assert len(set(q["options"])) == 4          # 无重复
    assert q["item"] == {"kind": "vocab", "id": 1}


def test_vocab_reading_q_basic():
    target = V(1, "高校", "こうこう", "高中")
    rng = random.Random(0)
    q = vocab_reading_q(target, _pool() + [target], rng)
    assert q["type"] == "reading"
    assert q["prompt"] == "高校"
    assert q["answer"] == "こうこう"
    assert q["answer"] in q["options"] and len(q["options"]) == 4


def test_vocab_reading_q_none_when_kana_only():
    target = V(1, "ラーメン", "ラーメン", "拉面")
    assert vocab_reading_q(target, _pool(), random.Random(0)) is None
