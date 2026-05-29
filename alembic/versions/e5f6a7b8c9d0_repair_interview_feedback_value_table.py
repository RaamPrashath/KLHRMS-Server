"""repair interview feedback value table drift

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-05-28 08:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_feedback_value (
            id VARCHAR(36) PRIMARY KEY,
            "feedbackId" VARCHAR(36) NOT NULL REFERENCES interview_feedback(id) ON DELETE CASCADE,
            "categoryId" VARCHAR(36) NOT NULL REFERENCES stage_evaluation_category(id) ON DELETE CASCADE,
            "numericValue" DOUBLE PRECISION,
            "textValue" TEXT,
            "booleanValue" BOOLEAN,
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_interview_feedback_value_category UNIQUE ("feedbackId", "categoryId")
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_interview_feedback_value_feedbackId"
        ON interview_feedback_value ("feedbackId")
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_interview_feedback_value_categoryId"
        ON interview_feedback_value ("categoryId")
        """
    )


def downgrade() -> None:
    pass
