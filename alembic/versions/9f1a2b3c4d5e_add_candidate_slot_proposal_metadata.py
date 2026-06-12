"""add candidate slot proposal metadata

Revision ID: 9f1a2b3c4d5e
Revises: 5e6f7a8b9c0d
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "9f1a2b3c4d5e"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE stage_event_proposed_slot ADD COLUMN IF NOT EXISTS "proposedBy" VARCHAR(32) NOT NULL DEFAULT \'INTERVIEWER\''
    )
    op.execute(
        'ALTER TABLE stage_event_proposed_slot ADD COLUMN IF NOT EXISTS "note" TEXT'
    )


def downgrade() -> None:
    op.execute('ALTER TABLE stage_event_proposed_slot DROP COLUMN IF EXISTS "note"')
    op.execute('ALTER TABLE stage_event_proposed_slot DROP COLUMN IF EXISTS "proposedBy"')
