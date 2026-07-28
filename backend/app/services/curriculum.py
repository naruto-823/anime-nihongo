from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

from app.models import (
    CurriculumItem,
    GrammarPoint,
    UserGrammarProgress,
    UserItemMastery,
    UserVocabProgress,
    Vocab,
)
from app.services.conjugation import conjugate

LEVELS = ["N5", "N4", "N3", "N2", "N1"]
MASTERY_THRESHOLD = 0.8


def vocab_dimensions(vocab: Vocab) -> list[str]:
    dimensions = ["meaning", "recall"]
    if vocab.headword != vocab.reading:
        dimensions.append("reading")
    table = conjugate(vocab.headword, vocab.reading, vocab.pos or "")
    if table:
        surfaces = {form["surface"] for form in table["forms"]
                    if form["key"] != "dictionary"}
        if len(surfaces) >= 4:
            dimensions.append("conjugation")
    return dimensions


def grammar_dimensions(_grammar: GrammarPoint) -> list[str]:
    return ["meaning", "recall"]


def sync_curriculum(db) -> int:
    """Make the syllabus ledger exactly cover every seeded N5-N1 item."""
    existing_vocab = {x.vocab_id: x for x in db.scalars(
        select(CurriculumItem).where(CurriculumItem.vocab_id.is_not(None))).all()}
    existing_grammar = {x.grammar_id: x for x in db.scalars(
        select(CurriculumItem).where(CurriculumItem.grammar_id.is_not(None))).all()}
    changed = 0
    for level in LEVELS:
        vocab = db.scalars(select(Vocab).where(Vocab.jlpt_level == level).order_by(Vocab.id)).all()
        grammar = db.scalars(select(GrammarPoint).where(
            GrammarPoint.jlpt_level == level).order_by(GrammarPoint.id)).all()
        for sequence, item in enumerate(vocab):
            values = {"level": level, "item_type": "vocab", "sequence": sequence,
                      "topic": f"{level}-vocab-zone-{sequence // 40 + 1}",
                      "required_dimensions": vocab_dimensions(item)}
            row = existing_vocab.get(item.id)
            if row is None:
                db.add(CurriculumItem(vocab_id=item.id, **values))
                changed += 1
            elif any(getattr(row, key) != value for key, value in values.items()):
                for key, value in values.items():
                    setattr(row, key, value)
                changed += 1
        for sequence, item in enumerate(grammar):
            values = {"level": level, "item_type": "grammar", "sequence": sequence,
                      "topic": f"{level}-grammar-zone-{sequence // 10 + 1}",
                      "required_dimensions": grammar_dimensions(item)}
            row = existing_grammar.get(item.id)
            if row is None:
                db.add(CurriculumItem(grammar_id=item.id, **values))
                changed += 1
            elif any(getattr(row, key) != value for key, value in values.items()):
                for key, value in values.items():
                    setattr(row, key, value)
                changed += 1
    if changed:
        db.commit()
    return changed


def backfill_legacy_mastery(db) -> int:
    """Preserve pre-ledger study history without inventing mastered answers.

    Old progress rows prove that an item was encountered, but not which quiz
    answer was correct. They therefore become meaning-practice evidence; real
    mastery continues to be earned by answering dimension-aware questions.
    """
    existing = {(row.user_id, row.item_type, row.item_id, row.dimension)
                for row in db.scalars(select(UserItemMastery)).all()}
    changed = 0
    sources = (
        ("vocab", db.scalars(select(UserVocabProgress)).all(), "vocab_id"),
        ("grammar", db.scalars(select(UserGrammarProgress)).all(), "grammar_id"),
    )
    for kind, rows, item_field in sources:
        for progress in rows:
            key = (progress.user_id, kind, getattr(progress, item_field), "meaning")
            if key in existing:
                continue
            attempts = max(1, progress.reps + progress.lapses)
            correct = min(progress.reps, attempts)
            db.add(UserItemMastery(
                user_id=progress.user_id,
                item_type=kind,
                item_id=getattr(progress, item_field),
                dimension="meaning",
                attempts=attempts,
                correct=correct,
                mastery=correct / attempts,
                last_seen_at=progress.last_reviewed,
            ))
            existing.add(key)
            changed += 1
    if changed:
        db.commit()
    return changed


def mastery_index(db, user_id: int, item_ids: dict[str, list[int]] | None = None):
    stmt = select(UserItemMastery).where(UserItemMastery.user_id == user_id)
    rows = db.scalars(stmt).all()
    allowed = None
    if item_ids is not None:
        allowed = {(kind, item_id) for kind, ids in item_ids.items() for item_id in ids}
    return {(row.item_type, row.item_id, row.dimension): row for row in rows
            if allowed is None or (row.item_type, row.item_id) in allowed}


def next_dimension(kind: str, item_id: int, dimensions: list[str], index) -> str:
    return min(dimensions, key=lambda dimension: (
        index.get((kind, item_id, dimension)).attempts
        if index.get((kind, item_id, dimension)) else 0,
        dimensions.index(dimension),
    ))


def record_mastery(db, user_id: int, kind: str, item_id: int,
                   dimension: str, correct: bool) -> UserItemMastery:
    row = db.scalars(select(UserItemMastery).where(
        UserItemMastery.user_id == user_id,
        UserItemMastery.item_type == kind,
        UserItemMastery.item_id == item_id,
        UserItemMastery.dimension == dimension,
    )).one_or_none()
    if row is None:
        row = UserItemMastery(user_id=user_id, item_type=kind, item_id=item_id,
                              dimension=dimension, attempts=0, correct=0, mastery=0.0)
        db.add(row)
    row.attempts += 1
    row.correct += int(correct)
    row.mastery = row.correct / row.attempts
    row.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return row


def coverage_report(db, user_id: int) -> dict:
    content_counts = defaultdict(lambda: defaultdict(int))
    for level, kind, count in (
        *[(level, "vocab", db.query(Vocab).filter_by(jlpt_level=level).count())
          for level in LEVELS],
        *[(level, "grammar", db.query(GrammarPoint).filter_by(jlpt_level=level).count())
          for level in LEVELS],
    ):
        content_counts[level][kind] = count

    curriculum = db.scalars(select(CurriculumItem)).all()
    mastery = mastery_index(db, user_id)
    levels = []
    total_required = total_practiced = total_mastered = 0
    for level in LEVELS:
        rows = [row for row in curriculum if row.level == level]
        required = sum(len(row.required_dimensions) for row in rows)
        practiced = mastered = 0
        for row in rows:
            item_id = row.vocab_id if row.item_type == "vocab" else row.grammar_id
            for dimension in row.required_dimensions:
                evidence = mastery.get((row.item_type, item_id, dimension))
                practiced += int(bool(evidence and evidence.attempts))
                mastered += int(bool(evidence and evidence.mastery >= MASTERY_THRESHOLD))
        mapped_vocab = sum(row.item_type == "vocab" for row in rows)
        mapped_grammar = sum(row.item_type == "grammar" for row in rows)
        missing = (content_counts[level]["vocab"] - mapped_vocab
                   + content_counts[level]["grammar"] - mapped_grammar)
        levels.append({
            "level": level,
            "vocab": {"total": content_counts[level]["vocab"], "mapped": mapped_vocab},
            "grammar": {"total": content_counts[level]["grammar"], "mapped": mapped_grammar},
            "missing_items": missing,
            "required_dimensions": required,
            "practiced_dimensions": practiced,
            "mastered_dimensions": mastered,
            "practice_percent": round(practiced / required * 100, 1) if required else 0.0,
            "mastery_percent": round(mastered / required * 100, 1) if required else 0.0,
        })
        total_required += required
        total_practiced += practiced
        total_mastered += mastered
    return {
        "syllabus_complete": all(level["missing_items"] == 0 for level in levels),
        "levels": levels,
        "totals": {
            "content_items": sum(x["vocab"]["total"] + x["grammar"]["total"] for x in levels),
            "required_dimensions": total_required,
            "practiced_dimensions": total_practiced,
            "mastered_dimensions": total_mastered,
            "practice_percent": round(total_practiced / total_required * 100, 1)
            if total_required else 0.0,
            "mastery_percent": round(total_mastered / total_required * 100, 1)
            if total_required else 0.0,
        },
    }
