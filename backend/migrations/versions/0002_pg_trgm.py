"""pg_trgm GIN index for vocab search (postgresql only)

Revision ID: 0002_pg_trgm
Revises: 0001_initial
"""
from alembic import op

revision = "0002_pg_trgm"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_COLS = ("headword", "reading", "meaning_zh")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for col in _COLS:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_vocab_{col}_trgm "
            f"ON vocab USING gin ({col} gin_trgm_ops)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for col in _COLS:
        op.execute(f"DROP INDEX IF EXISTS ix_vocab_{col}_trgm")
    # 扩展保留(可能被他处使用)
