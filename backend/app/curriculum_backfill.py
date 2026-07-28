from app.db import SessionLocal
from app.services.curriculum import (
    backfill_legacy_mastery,
    coverage_report,
    sync_curriculum,
)


def main() -> None:
    db = SessionLocal()
    try:
        mapped = sync_curriculum(db)
        legacy = backfill_legacy_mastery(db)
        report = coverage_report(db, 1)
        assert report["syllabus_complete"], report
        assert report["totals"]["content_items"] >= 11501, report["totals"]
        print({"mapped_now": mapped, "legacy_rows_now": legacy, **report["totals"]})
    finally:
        db.close()


if __name__ == "__main__":
    main()
