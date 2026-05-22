import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import GrammarPoint

SEED_PATH = Path(__file__).parent / "data" / "grammar_seed.json"
_REQUIRED_FIELDS = {"key", "name", "jlpt_level", "explanation"}


def load_grammar_seed(session: Session) -> int:
    """把 grammar_seed.json 写入数据库（按 key 幂等）。返回种子文件总条数（非本次插入数）。

    注意：函数仅在有新增条目时才调用 session.commit()；调用方不应在同一
    事务中留有其他未提交的改动。
    """
    entries = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for e in entries:
        if not _REQUIRED_FIELDS <= e.keys():
            raise ValueError(f"语法种子条目字段不全: {e!r}")
    existing = {k for (k,) in session.query(GrammarPoint.key).all()}
    new_entries = [e for e in entries if e["key"] not in existing]
    for e in new_entries:
        session.add(GrammarPoint(
            key=e["key"], name=e["name"], jlpt_level=e["jlpt_level"],
            explanation=e["explanation"], curated=True, status="locked",
        ))
    if new_entries:
        session.commit()
    return len(entries)
