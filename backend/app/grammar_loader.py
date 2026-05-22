import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import GrammarPoint

SEED_PATH = Path(__file__).parent / "data" / "grammar_seed.json"


def load_grammar_seed(session: Session) -> int:
    """把 grammar_seed.json 写入数据库（按 key 幂等）。返回种子总条数。"""
    entries = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    existing = {k for (k,) in session.query(GrammarPoint.key).all()}
    for e in entries:
        if e["key"] in existing:
            continue
        session.add(GrammarPoint(
            key=e["key"], name=e["name"], jlpt_level=e["jlpt_level"],
            explanation=e["explanation"], curated=True, status="locked",
        ))
    session.commit()
    return len(entries)
