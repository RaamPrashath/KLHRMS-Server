"""add interview rejection records

Revision ID: e1a2b3c4d5f6
Revises: d2e4f6a8b901
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e1a2b3c4d5f6"
down_revision: str | Sequence[str] | None = "d2e4f6a8b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_rejection_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("eventId", sa.String(length=36), nullable=False),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("rejectedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["eventId"], ["stage_event.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eventId", "memberId", name="uq_interview_rejection_event_member"),
    )
    op.create_index("ix_interview_rejection_record_eventId", "interview_rejection_record", ["eventId"])
    op.create_index("ix_interview_rejection_record_memberId", "interview_rejection_record", ["memberId"])
    op.create_index("ix_interview_rejection_record_organizationId", "interview_rejection_record", ["organizationId"])


def downgrade() -> None:
    op.drop_index("ix_interview_rejection_record_organizationId", table_name="interview_rejection_record")
    op.drop_index("ix_interview_rejection_record_memberId", table_name="interview_rejection_record")
    op.drop_index("ix_interview_rejection_record_eventId", table_name="interview_rejection_record")
    op.drop_table("interview_rejection_record")
