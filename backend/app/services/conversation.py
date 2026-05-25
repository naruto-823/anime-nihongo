import json

from app.services import llm

_TURN_SYSTEM = """你既要扮演动漫《{series}》第 {number} 集里的角色「{character}」与一位
中国 N2 学习者对话，又要在旁兼任他的日语口语老师。每收到他一句日语，请做两件事：

1) 用「{character}」的口吻、普通体（タメ口）、1–3 句日语自然回应，话题围绕这一集。
2) 对他最新一句发言做即时点评：
   - 若表达自然、或只是无伤大雅的小瑕疵：把 ok 设为 true，corrected / note 设为 null。
   - 若有语法、用词、语体（タメ口/敬语错配）等问题：把 ok 设为 false，给 corrected
     （更自然的日语完整改写）和 note（一句简短中文讲解，<=40 字）。
   - 完全无关或空话也算 ok=true，不要硬找毛病。

只返回 JSON，不要多余文字：
{{
  "reply": "你的日语回复",
  "critique": {{ "ok": true|false, "corrected": "..." 或 null, "note": "..." 或 null }}
}}"""

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
    """进行一轮角色对话。返回 {"reply": ..., "critique": {...}}。"""
    system = _TURN_SYSTEM.format(
        series=series_title, number=episode_number, character=character)
    convo = history + [{"role": "user", "text": user_text}]
    user = json.dumps({"对话历史": _history_text(convo)}, ensure_ascii=False)
    result = llm.call_json(system=system, user=user)
    raw_crit = result.get("critique") or {}
    critique = {
        "ok": bool(raw_crit.get("ok", True)),
        "corrected": raw_crit.get("corrected"),
        "note": raw_crit.get("note"),
    }
    return {"reply": result.get("reply", ""), "critique": critique}


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
