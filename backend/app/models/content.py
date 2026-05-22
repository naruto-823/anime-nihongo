from datetime import datetime

from sqlalchemy import JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    title_jp: Mapped[str | None]
    jimaku_entry_id: Mapped[int | None]
    is_current: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class Episode(Base):
    __tablename__ = "episode"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"))
    number: Mapped[int]
    title: Mapped[str | None]
    source: Mapped[str]  # jimaku / upload
    status: Mapped[str] = mapped_column(default="importing")  # importing/processing/ready/failed
    processed_lines: Mapped[int] = mapped_column(default=0)
    total_lines: Mapped[int] = mapped_column(default=0)
    read_position: Mapped[int] = mapped_column(default=0)
    reading_done: Mapped[bool] = mapped_column(default=False)
    imported_at: Mapped[datetime] = mapped_column(server_default=func.now())

    series: Mapped["Series"] = relationship(back_populates="episodes")
    lines: Mapped[list["Line"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan", order_by="Line.idx"
    )


class Line(Base):
    __tablename__ = "line"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episode.id"))
    idx: Mapped[int]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    speaker: Mapped[str | None]
    text_jp: Mapped[str]
    furigana: Mapped[list | None] = mapped_column(JSON, default=None)
    translation_zh: Mapped[str | None]
    grammar_notes: Mapped[list | None] = mapped_column(JSON, default=None)
    register_tag: Mapped[str | None]
    grammar_point_keys: Mapped[list | None] = mapped_column(JSON, default=None)
    processed: Mapped[bool] = mapped_column(default=False)

    episode: Mapped["Episode"] = relationship(back_populates="lines")
