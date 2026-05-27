"""add interview proposed slots and candidate token

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-05-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stage_event_proposed_slot (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            "eventId" VARCHAR(36) NOT NULL REFERENCES stage_event(id) ON DELETE CASCADE,
            "participantId" VARCHAR(36) NOT NULL REFERENCES stage_event_participant(id) ON DELETE CASCADE,
            "startTime" TIMESTAMPTZ NOT NULL,
            "endTime" TIMESTAMPTZ NOT NULL,
            "isSelectedByCandidate" BOOLEAN NOT NULL DEFAULT FALSE,
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS seps_eventId_idx ON stage_event_proposed_slot (\"eventId\")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS seps_participantId_idx ON stage_event_proposed_slot (\"participantId\")"
    )
    op.execute(
        'ALTER TABLE stage_event ADD COLUMN IF NOT EXISTS "candidateToken" VARCHAR UNIQUE'
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stage_event_proposed_slot CASCADE")
    op.execute('ALTER TABLE stage_event DROP COLUMN IF EXISTS "candidateToken"')
