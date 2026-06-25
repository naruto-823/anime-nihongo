from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import JSONB_OR_JSON, Base


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    title_jp: Mapped[str | None]
    jimaku_entry_id: Mapped[int | None]
    is_current: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    anilist_id: Mapped[int | None] = mapped_column(default=None)
    anilist_status: Mapped[str] = mapped_column(default="pending")
    characters: Mapped[list | None] = mapped_column(JSONB_OR_JSON, default=None)

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class Episode(Base):
    __tablename__ = "episode"
    __table_args__ = (UniqueConstraint("series_id", "number", name="uq_episode_series_number"),)

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
    scenes_split: Mapped[bool] = mapped_column(default=False)
    imported_at: Mapped[datetime] = mapped_column(server_default=func.now())

    series: Mapped["Series"] = relationship(back_populates="episodes")
    lines: Mapped[list["Line"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan", order_by="Line.idx"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan", order_by="Scene.idx"
    )


class Line(Base):
    __tablename__ = "line"
    __table_args__ = (UniqueConstraint("episode_id", "idx", name="uq_line_episode_idx"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episode.id"))
    idx: Mapped[int]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    speaker: Mapped[str | None]
    text_jp: Mapped[str]
    furigana: Mapped[list | None] = mapped_column(JSONB_OR_JSON, default=None)
    translation_zh: Mapped[str | None]
    grammar_notes: Mapped[list | None] = mapped_column(JSONB_OR_JSON, default=None)
    register_tag: Mapped[str | None]
    grammar_point_keys: Mapped[list | None] = mapped_column(JSONB_OR_JSON, default=None)
    processed: Mapped[bool] = mapped_column(default=False)

    episode: Mapped["Episode"] = relationship(back_populates="lines")


class Scene(Base):
    __tablename__ = "scene"
    __table_args__ = (UniqueConstraint("episode_id", "idx", name="uq_scene_episode_idx"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episode.id"))
    idx: Mapped[int]
    title_zh: Mapped[str]
    start_line_idx: Mapped[int]
    end_line_idx: Mapped[int]
    line_count: Mapped[int]

    episode: Mapped["Episode"] = relationship(back_populates="scenes")
