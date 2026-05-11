"""add interview meeting metadata

Revision ID: 3f7c4a9e2b11
Revises: 2d9f1b6c8a4e
Create Date: 2026-05-10 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3f7c4a9e2b11"
down_revision: Union[str, None] = "2d9f1b6c8a4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stage_event", sa.Column("googleCalendarEventId", sa.String(length=255), nullable=True))
    op.add_column("stage_event", sa.Column("googleCalendarEventUrl", sa.Text(), nullable=True))
    op.add_column("stage_event", sa.Column("emailSentAt", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_stage_event_googleCalendarEventId", "stage_event", ["googleCalendarEventId"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stage_event_googleCalendarEventId", table_name="stage_event")
    op.drop_column("stage_event", "emailSentAt")
    op.drop_column("stage_event", "googleCalendarEventUrl")
    op.drop_column("stage_event", "googleCalendarEventId")
