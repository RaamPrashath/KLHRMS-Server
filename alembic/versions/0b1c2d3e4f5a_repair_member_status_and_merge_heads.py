"""repair member status and merge active heads

Revision ID: 0b1c2d3e4f5a
Revises: a7d3e5f8b9c0, e8f1a2b3c4d5, c2d3e4f5a6b7
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0b1c2d3e4f5a"
down_revision: str | Sequence[str] | None = (
    "a7d3e5f8b9c0",
    "e8f1a2b3c4d5",
    "c2d3e4f5a6b7",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE member
            ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        """
    )


def downgrade() -> None:
    op.execute('ALTER TABLE member DROP COLUMN IF EXISTS status')
