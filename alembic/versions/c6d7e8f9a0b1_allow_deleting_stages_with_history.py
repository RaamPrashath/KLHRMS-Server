"""allow deleting stages with movement history

Revision ID: c6d7e8f9a0b1
Revises: b3c4d5e6f7a8
Create Date: 2026-06-16 15:25:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6d7e8f9a0b1"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "application_stage_history_toStageId_fkey",
        "application_stage_history",
        type_="foreignkey",
    )
    op.alter_column(
        "application_stage_history",
        "toStageId",
        existing_type=sa.String(length=36),
        nullable=True,
    )
    op.create_foreign_key(
        "application_stage_history_toStageId_fkey",
        "application_stage_history",
        "pipeline_stage",
        ["toStageId"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "application_stage_history_toStageId_fkey",
        "application_stage_history",
        type_="foreignkey",
    )
    op.execute('DELETE FROM application_stage_history WHERE "toStageId" IS NULL')
    op.alter_column(
        "application_stage_history",
        "toStageId",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.create_foreign_key(
        "application_stage_history_toStageId_fkey",
        "application_stage_history",
        "pipeline_stage",
        ["toStageId"],
        ["id"],
        ondelete="RESTRICT",
    )
