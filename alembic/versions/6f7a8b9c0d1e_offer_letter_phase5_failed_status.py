"""offer letter phase 5 failed status

Revision ID: 6f7a8b9c0d1e
Revises: 4d5e6f7a8b9d
Create Date: 2026-05-27 23:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "6f7a8b9c0d1e"
down_revision: str | Sequence[str] | None = "4d5e6f7a8b9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'offerstatus')
               AND NOT EXISTS (
                   SELECT 1
                   FROM pg_enum
                   WHERE enumlabel = 'FAILED'
                     AND enumtypid = 'offerstatus'::regtype
               ) THEN
                ALTER TYPE offerstatus ADD VALUE 'FAILED' AFTER 'SENT';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    pass
