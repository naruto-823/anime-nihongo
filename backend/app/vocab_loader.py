import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Vocab

SEED_PATH = Path(__file__).parent / "data" / "vocab_seed.json"
_REQUIRED_FIELDS = {"headword", "reading", "meaning_zh", "jlpt_level"}


def load_vocab_seed(session: Session) -> int:
    """把 vocab_seed.json 写入数据库（按 (headword, reading) 幂等）。返回种子文件总条数（非本次插入数）。

    注意：函数仅在有新增条目时才调用 session.commit()；调用方不应在同一
    事务中留有其他未提交的改动。
    """
    entries = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for e in entries:
        if not _REQUIRED_FIELDS <= e.keys():
            raise ValueError(f"词汇种子条目字段不全: {e!r}")
    existing = {(h, r) for (h, r) in session.query(Vocab.headword, Vocab.reading).all()}
    new_entries = [e for e in entries if (e["headword"], e["reading"]) not in existing]
    for e in new_entries:
        session.add(Vocab(
            headword=e["headword"], reading=e["reading"], meaning_zh=e["meaning_zh"],
            pos=e.get("pos"), jlpt_level=e["jlpt_level"],
        ))
    if new_entries:
        session.commit()
    return len(entries)
