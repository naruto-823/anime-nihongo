import json

from sqlalchemy.orm import Session

from app.models import Episode, GrammarPoint, Line, Scene, Vocab
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


_SCENE_SYSTEM = """你是动漫剧本场景切分助手。给定一集的全部台词，按对话聚集和角色切换切成 5–8 个场景（极少台词时 2–3 个也可）。
只返回 JSON 对象，不要多余文字。结构：
{"scenes": [{"title_zh": "5-10 字中文短标题", "start_idx": 整数, "end_idx": 整数}]}
要求：覆盖全部 idx 无空隙、无重叠；start_idx <= end_idx；title_zh 非空。"""


def _split_scenes(lines: list[Line]) -> list[dict]:
    """调 LLM 切场景，返回 [{title_zh, start_idx, end_idx}] 列表（未校验）。"""
    user = json.dumps({
        "lines": [{"idx": ln.idx, "text": ln.text_jp, "speaker": ln.speaker}
                  for ln in lines],
    }, ensure_ascii=False)
    result = llm.call_json(system=_SCENE_SYSTEM, user=user)
    return result.get("scenes") or []


def _validate_scenes(scenes: list[dict], total_lines: int) -> list[dict]:
    """校验场景列表覆盖性。失败抛 ValueError；返回按 start_idx 排序后的列表。"""
    if not scenes:
        raise ValueError("切场景返回空列表")
    ordered = sorted(scenes, key=lambda s: s.get("start_idx", -1))
    for sc in ordered:
        if not sc.get("title_zh"):
            raise ValueError(f"场景缺少 title_zh: {sc}")
        if sc.get("start_idx") is None or sc.get("end_idx") is None:
            raise ValueError(f"场景缺少 idx: {sc}")
        if sc["start_idx"] > sc["end_idx"]:
            raise ValueError(f"场景 start_idx > end_idx: {sc}")
    if ordered[0]["start_idx"] != 0:
        raise ValueError(f"首场景必须从 idx=0 开始: {ordered[0]}")
    if ordered[-1]["end_idx"] != total_lines - 1:
        raise ValueError(
            f"末场景必须到 idx={total_lines - 1}: {ordered[-1]}"
        )
    for prev, nxt in zip(ordered, ordered[1:]):
        if nxt["start_idx"] != prev["end_idx"] + 1:
            raise ValueError(
                f"场景之间空隙或重叠: prev.end={prev['end_idx']}, next.start={nxt['start_idx']}"
            )
    return ordered


def _write_scenes(session: Session, episode_id: int, scenes: list[dict]) -> None:
    for idx, sc in enumerate(scenes):
        session.add(Scene(
            episode_id=episode_id, idx=idx, title_zh=sc["title_zh"],
            start_line_idx=sc["start_idx"], end_line_idx=sc["end_idx"],
            line_count=sc["end_idx"] - sc["start_idx"] + 1,
        ))


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

    if not episode.scenes_split:
        all_lines = (
            session.query(Line)
            .filter_by(episode_id=episode_id)
            .order_by(Line.idx)
            .all()
        )
        try:
            raw_scenes = _split_scenes(all_lines)
            ordered = _validate_scenes(raw_scenes, episode.total_lines)
            _write_scenes(session, episode_id, ordered)
            episode.scenes_split = True
            session.commit()
        except Exception:
            try:
                session.rollback()
                ep = session.get(Episode, episode_id)
                if ep is not None:
                    ep.status = "failed"
                    session.commit()
            except Exception:
                pass
            raise

    grammar_index = _grammar_index(session)
    pending = (
        session.query(Line)
        .filter_by(episode_id=episode_id, processed=False)
        .order_by(Line.idx)
        .all()
    )

    try:
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            result = llm.call_json(
                system=_SYSTEM, user=_build_user(batch, grammar_index))
            by_idx = {item["idx"]: item for item in result.get("lines", [])}
            for ln in batch:
                # LLM 若漏掉某行 idx，该行仍标记 processed（注释留空），保持断点续跑干净
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
            episode.processed_lines = (
                session.query(Line)
                .filter_by(episode_id=episode_id, processed=True)
                .count()
            )
            session.commit()
        episode.status = "ready"
        session.commit()
    except Exception:
        # 出错时回滚脏事务，再独立把状态记为 failed，最后重新抛出原始异常
        try:
            session.rollback()
            ep = session.get(Episode, episode_id)
            if ep is not None:
                ep.status = "failed"
                session.commit()
        except Exception:
            pass
        raise
