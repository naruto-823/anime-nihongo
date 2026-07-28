"""per-user vocabulary and grammar learning state

Revision ID: 0004_user_study_progress
Revises: 0003_tower_users
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_user_study_progress"
down_revision = "0003_tower_users"
branch_labels = None
depends_on = None


def _progress_columns(item_name: str, target: str) -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(item_name, sa.Integer(), sa.ForeignKey(target, ondelete="CASCADE"), nullable=False),
        sa.Column("in_srs", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ease", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("last_reviewed", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "user_vocab_progress" not in existing:
        op.create_table(
            "user_vocab_progress",
            *_progress_columns("vocab_id", "vocab.id"),
            sa.UniqueConstraint("user_id", "vocab_id", name="uq_user_vocab_progress"),
        )
        op.create_index("ix_user_vocab_progress_user_id", "user_vocab_progress", ["user_id"])
        op.create_index("ix_user_vocab_progress_vocab_id", "user_vocab_progress", ["vocab_id"])
    if "user_grammar_progress" not in existing:
        op.create_table(
            "user_grammar_progress",
            *_progress_columns("grammar_id", "grammar_point.id"),
            sa.Column("status", sa.String(), nullable=False, server_default="learning"),
            sa.UniqueConstraint("user_id", "grammar_id", name="uq_user_grammar_progress"),
        )
        op.create_index("ix_user_grammar_progress_user_id", "user_grammar_progress", ["user_id"])
        op.create_index("ix_user_grammar_progress_grammar_id", "user_grammar_progress", ["grammar_id"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "user_grammar_progress" in existing:
        op.drop_table("user_grammar_progress")
    if "user_vocab_progress" in existing:
        op.drop_table("user_vocab_progress")
