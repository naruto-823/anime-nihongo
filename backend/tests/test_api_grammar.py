from app.models import GrammarPoint
from app.services import grammar_quiz


def test_checklist_groups_by_level(client, db_session):
    db_session.add_all([
        GrammarPoint(key="g-n2", name="〜N2点", jlpt_level="N2",
                     explanation="x", curated=True, status="locked"),
        GrammarPoint(key="g-n1", name="〜N1点", jlpt_level="N1",
                     explanation="y", curated=True, status="seen"),
    ])
    db_session.commit()
    body = client.get("/api/grammar/checklist").json()
    assert "N2" in body and "N1" in body
    assert body["N2"][0]["key"] == "g-n2"
    assert body["N1"][0]["status"] == "seen"


def test_grammar_quiz_endpoint(client, db_session, monkeypatch):
    monkeypatch.setattr(
        grammar_quiz.llm, "call_json",
        lambda **kw: {"quiz": [{"question": "Q?", "options": ["a", "b", "c", "d"],
                                "answer": "a", "explain": "e"}]})
    gp = GrammarPoint(key="g1", name="〜g1", jlpt_level="N2", explanation="x",
                      curated=True)
    db_session.add(gp)
    db_session.commit()
    body = client.get(f"/api/grammar/{gp.id}/quiz").json()
    assert body["answer"] == "a" and len(body["options"]) == 4
