"""canonical curriculum and per-dimension mastery

Revision ID: 0005_curriculum_mastery
Revises: 0004_user_study_progress
"""
import sqlalchemy as sa
from alembic import op

from app.db import JSONB_OR_JSON

revision = "0005_curriculum_mastery"
down_revision = "0004_user_study_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "curriculum_item" not in existing:
        op.create_table(
            "curriculum_item",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("level", sa.String(), nullable=False),
            sa.Column("item_type", sa.String(), nullable=False),
            sa.Column("vocab_id", sa.Integer(), sa.ForeignKey("vocab.id", ondelete="CASCADE")),
            sa.Column("grammar_id", sa.Integer(), sa.ForeignKey("grammar_point.id", ondelete="CASCADE")),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("topic", sa.String(), nullable=False),
            sa.Column("required_dimensions", JSONB_OR_JSON, nullable=False),
            sa.CheckConstraint(
                "(vocab_id IS NOT NULL AND grammar_id IS NULL) OR "
                "(vocab_id IS NULL AND grammar_id IS NOT NULL)",
                name="ck_curriculum_one_content",
            ),
            sa.UniqueConstraint("vocab_id", name="uq_curriculum_vocab"),
            sa.UniqueConstraint("grammar_id", name="uq_curriculum_grammar"),
            sa.UniqueConstraint("level", "item_type", "sequence", name="uq_curriculum_sequence"),
        )
        op.create_index("ix_curriculum_item_level", "curriculum_item", ["level"])
        op.create_index("ix_curriculum_item_item_type", "curriculum_item", ["item_type"])
    if "user_item_mastery" not in existing:
        op.create_table(
            "user_item_mastery",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_type", sa.String(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("dimension", sa.String(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("correct", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mastery", sa.Float(), nullable=False, server_default="0"),
            sa.Column("last_seen_at", sa.DateTime()),
            sa.UniqueConstraint("user_id", "item_type", "item_id", "dimension",
                                name="uq_user_item_dimension"),
        )
        op.create_index("ix_user_item_mastery_user_id", "user_item_mastery", ["user_id"])
        op.create_index("ix_user_item_mastery_item_type", "user_item_mastery", ["item_type"])
        op.create_index("ix_user_item_mastery_item_id", "user_item_mastery", ["item_id"])


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "user_item_mastery" in existing:
        op.drop_table("user_item_mastery")
    if "curriculum_item" in existing:
        op.drop_table("curriculum_item")
