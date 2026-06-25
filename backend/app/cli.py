import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import init_db, make_engine, make_session_factory
from app.grammar_loader import load_grammar_seed
from app.models import Episode, Line, Series
from app.services import pipeline
from app.services.subtitles import parse_subtitle
from app.vocab_loader import load_vocab_seed


def import_episode_from_file(session: Session, series_title: str, number: int,
                             file_path: str) -> Episode:
    """从本地字幕文件导入一集，落库 Series/Episode/Line（未加工）。"""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="ignore")
    parsed = parse_subtitle(content, path.suffix)

    if not parsed:
        raise ValueError(f"字幕文件未解析出任何台词，无法导入：{file_path}")

    series = session.query(Series).filter_by(title=series_title).first()
    if series is None:
        series = Series(title=series_title)
        session.add(series)
        session.flush()

    existing = (
        session.query(Episode)
        .filter_by(series_id=series.id, number=number)
        .first()
    )
    if existing is not None:
        raise ValueError(
            f"《{series_title}》第 {number} 集已存在（episode id={existing.id}）。"
            "请先删除它或换一个 --number。"
        )

    episode = Episode(series_id=series.id, number=number, source="upload",
                      status="processing", total_lines=len(parsed))
    for p in parsed:
        episode.lines.append(Line(
            idx=p.idx, start_ms=p.start_ms, end_ms=p.end_ms,
            speaker=p.speaker, text_jp=p.text, processed=False))
    session.add(episode)
    session.commit()
    return episode


def main() -> None:
    parser = argparse.ArgumentParser(description="追番日语 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("import-episode", help="从字幕文件导入并加工一集")
    imp.add_argument("--series", required=True)
    imp.add_argument("--number", type=int, required=True)
    imp.add_argument("--file", required=True)

    args = parser.parse_args()

    engine = make_engine(settings.database_url)
    init_db(engine)
    session = make_session_factory(engine)()
    try:
        load_grammar_seed(session)
        load_vocab_seed(session)
        if args.cmd == "import-episode":
            ep = import_episode_from_file(session, args.series, args.number, args.file)
            print(f"已导入 episode id={ep.id}，{ep.total_lines} 行。开始加工…")
            pipeline.process_episode(session, ep.id)
            print(f"加工完成，状态={ep.status}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
