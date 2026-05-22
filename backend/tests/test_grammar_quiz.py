from app.models import GrammarPoint
from app.services import grammar_quiz


def _fake_quiz_llm(system, user, model=None, max_tokens=8000):
    return {"quiz": [
        {"question": "下線部に入るのは？　努力___、成功はない。",
         "options": ["なくして", "ながら", "ばかり", "つつ"],
         "answer": "なくして", "explain": "〜なくして（は）表示必要条件"},
        {"question": "「努力なくして成功なし」の意味は？",
         "options": ["不努力就没有成功", "努力很累", "成功很难", "努力之后"],
         "answer": "不努力就没有成功", "explain": "强调必要条件"},
    ]}


def test_get_quiz_generates_and_caches(db_session, monkeypatch):
    monkeypatch.setattr(grammar_quiz.llm, "call_json", _fake_quiz_llm)
    gp = GrammarPoint(key="nakushite", name="〜なくして", jlpt_level="N1",
                      explanation="没有…就（没有）", curated=True)
    db_session.add(gp)
    db_session.commit()

    q1 = grammar_quiz.get_quiz(db_session, gp)
    assert q1["answer"] == "なくして" or q1["answer"] == "不努力就没有成功"
    assert gp.quiz_cache is not None and len(gp.quiz_cache) >= 1
    # 第二次从缓存取，不再调用 LLM
    monkeypatch.setattr(grammar_quiz.llm, "call_json",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("不应再调用")))
    q2 = grammar_quiz.get_quiz(db_session, gp)
    assert "question" in q2


def test_get_quiz_regenerates_when_cache_empty(db_session, monkeypatch):
    calls = []

    def counting(system, user, model=None, max_tokens=8000):
        calls.append(1)
        return _fake_quiz_llm(system, user)

    monkeypatch.setattr(grammar_quiz.llm, "call_json", counting)
    gp = GrammarPoint(key="nakushite", name="〜なくして", jlpt_level="N1",
                      explanation="没有…就", curated=True, quiz_cache=[])
    db_session.add(gp)
    db_session.commit()
    grammar_quiz.get_quiz(db_session, gp)
    assert len(calls) == 1
