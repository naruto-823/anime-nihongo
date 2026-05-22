from datetime import date

from app.models import Vocab
from app.services.srs import (
    MASTERED_INTERVAL,
    SrsState,
    apply_review,
    is_mastered,
    next_state,
)


def test_new_card_good_then_good():
    s = next_state(SrsState(2.5, 0, 0, 0), "good")
    assert s.interval_days == 1 and s.reps == 1
    s2 = next_state(s, "good")
    assert s2.interval_days == 6 and s2.reps == 2


def test_again_resets_and_drops_ease():
    s = next_state(SrsState(2.5, 30, 5, 0), "again")
    assert s.interval_days == 0 and s.reps == 0 and s.lapses == 1
    assert abs(s.ease - 2.30) < 1e-9


def test_ease_floor():
    s = SrsState(1.3, 10, 3, 0)
    assert next_state(s, "again").ease == 1.3  # 不低于 1.3


def test_good_mature_multiplies_by_ease():
    s = next_state(SrsState(2.5, 10, 4, 0), "good")
    assert s.interval_days == 25  # round(10 * 2.5)


def test_easy_new_card():
    s = next_state(SrsState(2.5, 0, 0, 0), "easy")
    assert s.interval_days == 4 and abs(s.ease - 2.65) < 1e-9


def test_unknown_grade_raises():
    import pytest
    with pytest.raises(ValueError):
        next_state(SrsState(2.5, 0, 0, 0), "perfect")


def test_apply_review_mutates_model(db_session):
    v = Vocab(headword="本", reading="ほん", meaning_zh="书", in_srs=True)
    db_session.add(v)
    db_session.commit()
    apply_review(v, "good", today=date(2026, 5, 22))
    assert v.interval_days == 1
    assert v.due_date == date(2026, 5, 23)
    assert v.last_reviewed is not None


def test_is_mastered():
    assert is_mastered(SrsState(2.5, MASTERED_INTERVAL, 5, 0)) is True
    assert is_mastered(SrsState(2.5, 5, 2, 0)) is False
