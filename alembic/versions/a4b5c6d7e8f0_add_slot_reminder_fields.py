"""add slot invitation and reminder tracking fields

Revision ID: a4b5c6d7e8f0
Revises: 9f1a2b3c4d5e, bb12cc34dd56, e6f7a8b9c0d2
Create Date: 2026-06-11 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a4b5c6d7e8f0"
down_revision: tuple[str, str, str] = (
    "9f1a2b3c4d5e",
    "bb12cc34dd56",
    "e6f7a8b9c0d2",
)
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stage_event",
        sa.Column("slotInvitationSentAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "stage_event",
        sa.Column("lastSlotReminderSentAt", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stage_event", "lastSlotReminderSentAt")
    op.drop_column("stage_event", "slotInvitationSentAt")
