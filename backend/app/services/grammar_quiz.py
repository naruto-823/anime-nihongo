import random

from sqlalchemy.orm import Session

from app.models import GrammarPoint
from app.services import llm

_SYSTEM = """你是日语语法出题助手。给定一个语法点，出 4 道面向 N2 学习者的小测题。
只返回 JSON 对象，不要多余文字。结构：
{"quiz": [
  {"question": "题干（可含填空线 ___）",
   "options": ["选项1","选项2","选项3","选项4"],
   "answer": "正确选项的文本（必须与 options 之一完全一致）",
   "explain": "简短中文讲解"}
]}
题目要考查该语法点的用法，options 必须有且仅有 4 个，answer 必须是其中之一。"""


def _generate(point: GrammarPoint) -> list[dict]:
    user = f"语法点：{point.name}\nJLPT：{point.jlpt_level}\n释义：{point.explanation}"
    result = llm.call_json(system=_SYSTEM, user=user)
    quiz = result.get("quiz", [])
    return [q for q in quiz if q.get("question") and q.get("answer")]


def get_quiz(session: Session, point: GrammarPoint) -> dict:
    """取该语法点的一道小测题。缓存空/耗尽时经 LLM 生成并写入 quiz_cache。"""
    cache = point.quiz_cache or []
    if not cache:
        cache = _generate(point)
        if not cache:
            raise RuntimeError(f"语法点 {point.key} 小测生成失败")
        point.quiz_cache = cache
        session.commit()
    return random.choice(cache)
