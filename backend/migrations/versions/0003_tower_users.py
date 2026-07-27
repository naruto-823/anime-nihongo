"""tower users and per-user progress

Revision ID: 0003_tower_users
Revises: 0002_pg_trgm
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_tower_users"
down_revision = "0002_pg_trgm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("username"),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    tower_columns = {c["name"] for c in inspector.get_columns("tower_progress")}
    if "user_id" not in tower_columns:
        op.add_column("tower_progress", sa.Column("user_id", sa.Integer(), nullable=False,
                                                   server_default="1"))
        op.create_index("ix_tower_progress_user_id", "tower_progress", ["user_id"])
        if bind.dialect.name == "postgresql":
            op.drop_constraint("uq_tower_cell", "tower_progress", type_="unique")
            op.create_unique_constraint(
                "uq_tower_cell", "tower_progress",
                ["user_id", "level", "zone_idx", "stage_idx", "is_boss"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    # 0001_initial uses current metadata in SQLite test databases, so these
    # columns/tables already belong to the base schema there.
    if bind.dialect.name == "sqlite":
        return
    inspector = sa.inspect(bind)
    tower_columns = {c["name"] for c in inspector.get_columns("tower_progress")}
    if "user_id" in tower_columns:
        if bind.dialect.name == "postgresql":
            op.drop_constraint("uq_tower_cell", "tower_progress", type_="unique")
            op.create_unique_constraint(
                "uq_tower_cell", "tower_progress",
                ["level", "zone_idx", "stage_idx", "is_boss"],
            )
        op.drop_index("ix_tower_progress_user_id", table_name="tower_progress")
        op.drop_column("tower_progress", "user_id")
    if "users" in inspector.get_table_names():
        op.drop_index("ix_users_username", table_name="users")
        op.drop_table("users")
