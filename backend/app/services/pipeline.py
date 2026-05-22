import json

from sqlalchemy.orm import Session

from app.models import Episode, GrammarPoint, Line, Vocab
from app.services import llm
from app.services.tokenizer import to_furigana

_SYSTEM = """你是日语教学助手。给定动漫台词，逐句产出面向中文母语 N2 学习者的标注。
只返回 JSON 对象，不要多余文字。结构：
{
  "lines": [
    {"idx": 整数, "translation_zh": "中文翻译",
     "grammar_notes": [{"point": "语法点名", "explain": "中文讲解"}],
     "register_tag": "polite|casual|rough|feminine|dialect|archaic 之一",
     "grammar_point_keys": ["命中下方语法清单的 key，可空数组"]}
  ],
  "vocab": [{"headword": "辞书形", "reading": "假名", "meaning_zh": "中文释义",
             "pos": "词性", "jlpt_level": "N5..N1 或 null"}]
}
对 register_tag 为 rough/feminine/dialect 的句子，在 grammar_notes 里附一条现实礼貌场合的等价说法。"""


def _build_user(batch: list[Line], grammar_index: list[dict]) -> str:
    return json.dumps({
        "grammar_checklist": grammar_index,
        "lines": [{"idx": ln.idx, "text": ln.text_jp} for ln in batch],
    }, ensure_ascii=False)


def _grammar_index(session: Session) -> list[dict]:
    rows = session.query(GrammarPoint.key, GrammarPoint.name).filter_by(curated=True).all()
    return [{"key": k, "name": n} for k, n in rows]


def _upsert_vocab(session: Session, items: list[dict], source_line_id: int) -> None:
    for it in items:
        hw, rd = it.get("headword"), it.get("reading")
        if not hw or not rd:
            continue
        exists = session.query(Vocab).filter_by(headword=hw, reading=rd).first()
        if exists:
            continue
        session.add(Vocab(
            headword=hw, reading=rd, meaning_zh=it.get("meaning_zh", ""),
            pos=it.get("pos"), jlpt_level=it.get("jlpt_level"),
            source_line_id=source_line_id, in_srs=False,
        ))


def _mark_grammar_seen(session: Session, keys: list[str], source_line_id: int) -> None:
    for key in keys:
        gp = session.query(GrammarPoint).filter_by(key=key).first()
        if gp and gp.status == "locked":
            gp.status = "seen"
            gp.source_line_id = source_line_id


def process_episode(session: Session, episode_id: int, batch_size: int = 15) -> None:
    """加工一集：分批处理未加工的行。可重复调用（断点续跑）。"""
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise ValueError(f"episode {episode_id} 不存在")
    episode.status = "processing"
    session.commit()

    grammar_index = _grammar_index(session)
    pending = [ln for ln in episode.lines if not ln.processed]

    try:
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            result = llm.call_json(
                system=_SYSTEM, user=_build_user(batch, grammar_index))
            by_idx = {item["idx"]: item for item in result.get("lines", [])}
            for ln in batch:
                ann = by_idx.get(ln.idx, {})
                ln.furigana = to_furigana(ln.text_jp)
                ln.translation_zh = ann.get("translation_zh")
                ln.grammar_notes = ann.get("grammar_notes") or []
                ln.register_tag = ann.get("register_tag")
                keys = ann.get("grammar_point_keys") or []
                ln.grammar_point_keys = keys
                ln.processed = True
                session.flush()  # 取得 ln.id
                _mark_grammar_seen(session, keys, ln.id)
            # vocab 归到该批首行作为语境来源
            if batch:
                _upsert_vocab(session, result.get("vocab", []), batch[0].id)
            episode.processed_lines = sum(1 for x in episode.lines if x.processed)
            session.commit()
        episode.status = "ready"
        session.commit()
    except Exception:
        episode.status = "failed"
        session.commit()
        raise
