"""remove candidate user foreign key

Revision ID: c1d2e3f4a5b6
Revises: 9bc8279279dd
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "9bc8279279dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('ALTER TABLE "candidate" DROP CONSTRAINT IF EXISTS "candidate_userId_fkey"')
    op.execute('DROP INDEX IF EXISTS "ix_candidate_userId"')
    op.execute('DROP INDEX IF EXISTS "candidate_userId_idx"')
    op.execute('ALTER TABLE "candidate" DROP COLUMN IF EXISTS "userId"')


def downgrade() -> None:
    op.add_column("candidate", sa.Column("userId", sa.String(length=36), nullable=True))
    op.create_index("candidate_userId_idx", "candidate", ["userId"], unique=False)
    op.create_foreign_key(
        "candidate_userId_fkey",
        "candidate",
        "user",
        ["userId"],
        ["id"],
        ondelete="SET NULL",
    )
