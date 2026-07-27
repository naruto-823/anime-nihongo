from datetime import datetime

from sqlalchemy import UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TowerProgress(Base):
    __tablename__ = "tower_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "level", "zone_idx", "stage_idx", "is_boss",
                         name="uq_tower_cell"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(default=1, index=True)
    level: Mapped[str]
    zone_idx: Mapped[int]
    stage_idx: Mapped[int]
    is_boss: Mapped[bool] = mapped_column(default=False)
    cleared: Mapped[bool] = mapped_column(default=False)
    stars: Mapped[int] = mapped_column(default=0)
    best_accuracy: Mapped[float] = mapped_column(default=0.0)
    attempts: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    total_xp: Mapped[int] = mapped_column(default=0)
    player_level: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
