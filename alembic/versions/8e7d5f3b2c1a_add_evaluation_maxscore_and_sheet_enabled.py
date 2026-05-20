"""add evaluation maxScore and sheetEnabled

Revision ID: 8e7d5f3b2c1a
Revises: fa7c2d1e9b44
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "8e7d5f3b2c1a"
down_revision = "fa7c2d1e9b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add maxScore column to stage_evaluation_category (nullable integer, for "out of" scoring)
    op.add_column(
        "stage_evaluation_category",
        sa.Column("maxScore", sa.Integer(), nullable=True),
    )

    # Add sheetEnabled column to pipeline_stage (boolean, default false)
    op.add_column(
        "pipeline_stage",
        sa.Column(
            "sheetEnabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Set existing rows to have sheetEnabled = false (the default)
    op.alter_column("pipeline_stage", "sheetEnabled", server_default=None)


def downgrade() -> None:
    op.drop_column("pipeline_stage", "sheetEnabled")
    op.drop_column("stage_evaluation_category", "maxScore")
