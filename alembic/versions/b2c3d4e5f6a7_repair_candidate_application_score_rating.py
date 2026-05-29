"""repair candidate application score/rating drift

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-28 08:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidate_application
            ADD COLUMN IF NOT EXISTS score INTEGER,
            ADD COLUMN IF NOT EXISTS rating INTEGER
        """
    )


def downgrade() -> None:
    pass
