from datetime import date as _date
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import JSONB_OR_JSON, Base


class Vocab(Base):
    __tablename__ = "vocab"
    __table_args__ = (UniqueConstraint("headword", "reading", name="uq_vocab_word"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    headword: Mapped[str]
    reading: Mapped[str]
    meaning_zh: Mapped[str]
    pos: Mapped[str | None]
    jlpt_level: Mapped[str | None]
    source_line_id: Mapped[int | None] = mapped_column(ForeignKey("line.id"))
    in_srs: Mapped[bool] = mapped_column(default=False)
    ease: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(default=0)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[_date | None]
    last_reviewed: Mapped[datetime | None]


class GrammarPoint(Base):
    __tablename__ = "grammar_point"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    jlpt_level: Mapped[str]
    explanation: Mapped[str]
    curated: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="locked")  # locked/seen/learning
    quiz_cache: Mapped[list | None] = mapped_column(JSONB_OR_JSON, default=None)
    source_line_id: Mapped[int | None] = mapped_column(ForeignKey("line.id"))
    in_srs: Mapped[bool] = mapped_column(default=False)
    ease: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(default=0)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[_date | None]
    last_reviewed: Mapped[datetime | None]


class DailySession(Base):
    __tablename__ = "daily_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[_date] = mapped_column(unique=True)
    completed: Mapped[bool] = mapped_column(default=False)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episode.id"))
    vocab_reviewed: Mapped[int] = mapped_column(default=0)
    grammar_reviewed: Mapped[int] = mapped_column(default=0)
    lines_read: Mapped[int] = mapped_column(default=0)
    conversation_turns: Mapped[int] = mapped_column(default=0)
    summary: Mapped[dict | None] = mapped_column(JSONB_OR_JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB_OR_JSON)
