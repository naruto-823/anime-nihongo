from dataclasses import dataclass
from datetime import date, datetime, timedelta

GRADES = ("again", "hard", "good", "easy")
_MIN_EASE = 1.3
MASTERED_INTERVAL = 21  # interval_days ≥ 此值视为「已掌握」


@dataclass
class SrsState:
    ease: float
    interval_days: int
    reps: int
    lapses: int


def next_state(state: SrsState, grade: str) -> SrsState:
    """按 SM-2 计算下一个 SRS 状态。grade ∈ GRADES。"""
    if grade not in GRADES:
        raise ValueError(f"未知评分: {grade}")
    ease, interval, reps, lapses = (
        state.ease, state.interval_days, state.reps, state.lapses)
    if grade == "again":
        return SrsState(max(_MIN_EASE, ease - 0.20), 0, 0, lapses + 1)
    if grade == "hard":
        new_interval = 1 if reps == 0 else max(1, round(interval * 1.2))
        return SrsState(max(_MIN_EASE, ease - 0.15), new_interval, reps + 1, lapses)
    if grade == "good":
        if reps == 0:
            new_interval = 1
        elif reps == 1:
            new_interval = 6
        else:
            new_interval = max(1, round(interval * ease))
        return SrsState(ease, new_interval, reps + 1, lapses)
    # easy
    new_ease = ease + 0.15
    if reps == 0:
        new_interval = 4
    elif reps == 1:
        new_interval = 10
    else:
        new_interval = max(1, round(interval * new_ease * 1.3))
    return SrsState(new_ease, new_interval, reps + 1, lapses)


def is_mastered(state: SrsState) -> bool:
    return state.interval_days >= MASTERED_INTERVAL


def apply_review(item, grade: str, today: date | None = None) -> None:
    """把一次复习评分应用到 Vocab / GrammarPoint 模型对象（鸭子类型）。"""
    today = today or date.today()
    st = next_state(
        SrsState(item.ease, item.interval_days, item.reps, item.lapses), grade)
    item.ease = st.ease
    item.interval_days = st.interval_days
    item.reps = st.reps
    item.lapses = st.lapses
    item.due_date = today + timedelta(days=st.interval_days)
    item.last_reviewed = datetime.now()
