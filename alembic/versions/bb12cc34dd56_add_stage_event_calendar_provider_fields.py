"""add provider-neutral stage event calendar fields

Revision ID: bb12cc34dd56
Revises: 461e502394e6, 5da32dba2776
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "bb12cc34dd56"
down_revision: tuple[str, str] = ("461e502394e6", "5da32dba2776")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stage_event", sa.Column("calendarProvider", sa.String(length=32), nullable=True))
    op.add_column("stage_event", sa.Column("calendarEventId", sa.String(length=255), nullable=True))
    op.add_column("stage_event", sa.Column("calendarEventUrl", sa.Text(), nullable=True))
    op.add_column("stage_event", sa.Column("microsoftCalendarEventId", sa.String(length=255), nullable=True))
    op.add_column("stage_event", sa.Column("microsoftCalendarEventUrl", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stage_event", "microsoftCalendarEventUrl")
    op.drop_column("stage_event", "microsoftCalendarEventId")
    op.drop_column("stage_event", "calendarEventUrl")
    op.drop_column("stage_event", "calendarEventId")
    op.drop_column("stage_event", "calendarProvider")
