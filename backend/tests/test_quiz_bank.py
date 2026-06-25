import random

from app.services.quiz_bank import (
    grammar_meaning_q,
    make_grammar_question,
    make_vocab_question,
    vocab_conjugation_q,
    vocab_meaning_q,
    vocab_reading_q,
)


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


def test_vocab_conjugation_q_godan():
    target = V(1, "飲む", "のむ", "喝", pos="他動1")
    q = vocab_conjugation_q(target, random.Random(0))
    assert q["type"] == "conjugation"
    assert q["prompt"] == "飲む"
    assert q["hint"].endswith("形") or "形" in q["hint"]      # 目标活用形标签
    assert q["answer"] in q["options"] and len(q["options"]) == 4
    assert len(set(q["options"])) == 4
    # 答案应为该词某活用形的表层
    from app.services.conjugation import conjugate
    surfaces = {f["surface"] for f in conjugate("飲む", "のむ", "他動1")["forms"]}
    assert q["answer"] in surfaces


def test_vocab_conjugation_q_none_for_noun():
    target = V(1, "天気", "てんき", "天气", pos="名")
    assert vocab_conjugation_q(target, random.Random(0)) is None


class G:
    def __init__(self, id, name, explanation):
        self.id = id; self.name = name; self.explanation = explanation


def _gpool():
    return [G(i, f"〜语法{i}", f"含义{i}") for i in range(1, 8)]


def test_grammar_meaning_q():
    target = G(1, "〜にあたって", "在…之际")
    q = grammar_meaning_q(target, _gpool() + [target], random.Random(0))
    assert q["type"] == "grammar"
    assert q["prompt"] == "〜にあたって"
    assert q["answer"] == "在…之际" and len(q["options"]) == 4
    assert q["item"] == {"kind": "grammar", "id": 1}


def test_make_vocab_question_always_returns():
    target = V(1, "天気", "てんき", "天气", pos="名")   # 仅 meaning 可用
    q = make_vocab_question(target, _pool() + [target], random.Random(0))
    assert q["type"] in {"meaning", "reading", "conjugation"}
    assert q["item"]["kind"] == "vocab"


def test_make_grammar_question():
    target = G(1, "〜にあたって", "在…之际")
    assert make_grammar_question(target, _gpool() + [target], random.Random(0))["type"] == "grammar"
