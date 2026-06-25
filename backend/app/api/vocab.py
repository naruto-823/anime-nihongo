from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vocab
from app.services.conjugation import conjugate
from app.services.jpos import normalize_pos

router = APIRouter(prefix="/api/vocab", tags=["vocab"])

_LEVELS = ("N5", "N4", "N3", "N2", "N1")
# N5→N1 教学顺序排序；无等级（项目自建词）排最后
_LEVEL_ORDER = case(
    {lv: i for i, lv in enumerate(_LEVELS)}, value=Vocab.jlpt_level, else_=99
)


def _pos_filter_clause(db: Session, pos_key: str):
    """把词性筛选键转成 SQL 条件。

    归一化是 Python 侧逻辑,故先取所有 distinct pos(数量有限,约数百),
    归类后落成 `pos IN (...)`,从而与 SQL 分页/计数/其他筛选共存。
    """
    matching: list[str] = []
    has_null = False
    for (p,) in db.execute(select(Vocab.pos).distinct()).all():
        if p is None:
            has_null = pos_key == "other"
            continue
        if pos_key in normalize_pos(p)["filters"]:
            matching.append(p)
    clause = Vocab.pos.in_(matching)
    if has_null:
        clause = or_(clause, Vocab.pos.is_(None))
    return clause


@router.get("")
def list_vocab(
    db: Session = Depends(get_db),
    level: str | None = Query(default=None),
    q: str | None = Query(default=None),
    pos: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """词汇表分页浏览。level 按 JLPT 等级筛选；q 模糊搜写法/读音/中文释义；
    pos 按归一化词性筛选(noun/verb/verb_t/verb_i/i-adj/na-adj/adverb/other)。

    counts 反映 q + pos 过滤后、各等级的命中数(不受 level 限制),供等级筛选标签展示。
    """
    q = (q or "").strip()
    search = None
    if q:
        like = f"%{q}%"
        search = or_(
            Vocab.headword.like(like),
            Vocab.reading.like(like),
            Vocab.meaning_zh.like(like),
        )
    pos_clause = _pos_filter_clause(db, pos) if pos else None

    def _apply(stmt):
        if search is not None:
            stmt = stmt.where(search)
        if pos_clause is not None:
            stmt = stmt.where(pos_clause)
        return stmt

    # 各等级命中数(受 q + pos 影响,不受 level 影响)
    counts_stmt = _apply(select(Vocab.jlpt_level, func.count()).group_by(Vocab.jlpt_level))
    raw_counts = dict(db.execute(counts_stmt).all())
    counts = {lv: int(raw_counts.get(lv, 0)) for lv in _LEVELS}

    # 列表查询(受 level + q + pos 影响)
    stmt = _apply(select(Vocab))
    if level:
        stmt = stmt.where(Vocab.jlpt_level == level)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(_LEVEL_ORDER, Vocab.id).limit(limit).offset(offset)
    ).all()

    items = [_serialize(v) for v in rows]
    return {"total": int(total), "counts": counts, "items": items}


@router.get("/{vocab_id}")
def get_vocab(vocab_id: int, db: Session = Depends(get_db)) -> dict:
    """单词详情:词条 + 词性标签 + 活用表(不变形则 conjugation=null)。"""
    v = db.get(Vocab, vocab_id)
    if v is None:
        raise HTTPException(404, "词汇不存在")
    data = _serialize(v)
    data["conjugation"] = conjugate(v.headword, v.reading, v.pos or "")
    return data


def _serialize(v: Vocab) -> dict:
    return {
        "id": v.id, "headword": v.headword, "reading": v.reading,
        "meaning_zh": v.meaning_zh, "pos": v.pos,
        "pos_tags": normalize_pos(v.pos or "")["tags"],
        "jlpt_level": v.jlpt_level, "in_srs": v.in_srs,
    }
