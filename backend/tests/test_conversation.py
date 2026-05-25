from app.services import conversation


def _fake_turn_llm(system, user, model=None, max_tokens=8000):
    assert "アキラ" in system  # 角色名进了 system
    return {
        "reply": "うん、面白かったね。君はどう思った？",
        "critique": {"ok": False, "corrected": "面白かった",
                     "note": "「思う」前用普通形即可"},
    }


def _fake_feedback_llm(system, user, model=None, max_tokens=8000):
    return {
        "corrections": [
            {"original": "私は思う面白い", "fixed": "面白いと思う",
             "explain": "「と思う」前面用普通形"}
        ],
        "suggestions": ["可以多用「〜と思う」表达看法"],
        "new_vocab": [{"headword": "感想", "reading": "かんそう", "meaning_zh": "感想"}],
        "weak_grammar_keys": ["to-omou"],
    }


def test_converse_returns_reply(monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json", _fake_turn_llm)
    out = conversation.converse(
        series_title="サンプル", episode_number=1, character="アキラ",
        history=[{"role": "user", "text": "今日のエピソードどうだった？"}],
        user_text="面白かったよ")
    assert out["reply"].startswith("うん")
    assert out["critique"]["ok"] is False
    assert out["critique"]["corrected"] == "面白かった"


def test_converse_defaults_critique_to_ok(monkeypatch):
    monkeypatch.setattr(
        conversation.llm, "call_json",
        lambda **kw: {"reply": "ええ。"})  # no critique key at all
    out = conversation.converse(
        series_title="サンプル", episode_number=1, character="アキラ",
        history=[], user_text="こんにちは")
    assert out["critique"]["ok"] is True
    assert out["critique"]["corrected"] is None


def test_conversation_feedback_structure(monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json", _fake_feedback_llm)
    fb = conversation.conversation_feedback(
        series_title="サンプル", episode_number=1,
        history=[{"role": "user", "text": "私は思う面白い"}])
    assert fb["corrections"][0]["fixed"] == "面白いと思う"
    assert fb["weak_grammar_keys"] == ["to-omou"]
    assert fb["new_vocab"][0]["headword"] == "感想"
