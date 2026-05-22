import json

from app.services import llm

_TURN_SYSTEM = """你在用日语和一名中国 N2 学习者做口语对话练习。
你要扮演动漫《{series}》第 {number} 集里的角色「{character}」，用该角色的口吻、
普通体（タメ口）自然对话，话题围绕这一集的剧情。每次只回 1–3 句，口语化，
适当反问以推动对话。只返回 JSON：{{"reply": "你的日语回复"}}。"""

_FEEDBACK_SYSTEM = """你是日语口语老师。下面是一名中国 N2 学习者在围绕动漫
《{series}》第 {number} 集的对话中说过的日语。请复盘他的发言，只返回 JSON 对象：
{{
  "corrections": [{{"original": "原句", "fixed": "更自然的说法", "explain": "中文讲解"}}],
  "suggestions": ["中文改进建议"],
  "new_vocab": [{{"headword": "辞书形", "reading": "假名", "meaning_zh": "中文释义"}}],
  "weak_grammar_keys": ["从对话暴露出的薄弱语法点，用 kebab-case key，可空"]
}}
只针对学习者（role=user）的发言点评。"""


def _history_text(history: list[dict]) -> str:
    role_label = {"user": "学习者", "assistant": "角色"}
    return "\n".join(
        f"{role_label.get(h['role'], h['role'])}: {h['text']}" for h in history)


def converse(series_title: str, episode_number: int, character: str,
             history: list[dict], user_text: str) -> dict:
    """进行一轮角色对话。history 为既往轮次，user_text 为本轮用户发言。返回 {"reply": ...}。"""
    system = _TURN_SYSTEM.format(
        series=series_title, number=episode_number, character=character)
    convo = history + [{"role": "user", "text": user_text}]
    user = json.dumps({"对话历史": _history_text(convo)}, ensure_ascii=False)
    result = llm.call_json(system=system, user=user)
    return {"reply": result.get("reply", "")}


def conversation_feedback(series_title: str, episode_number: int,
                          history: list[dict]) -> dict:
    """对整段对话里学习者的发言做复盘反馈。"""
    system = _FEEDBACK_SYSTEM.format(series=series_title, number=episode_number)
    user = json.dumps({"对话历史": _history_text(history)}, ensure_ascii=False)
    result = llm.call_json(system=system, user=user)
    return {
        "corrections": result.get("corrections", []),
        "suggestions": result.get("suggestions", []),
        "new_vocab": result.get("new_vocab", []),
        "weak_grammar_keys": result.get("weak_grammar_keys", []),
    }
