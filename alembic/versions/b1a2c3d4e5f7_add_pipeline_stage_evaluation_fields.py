"""add pipeline_stage evaluation fields and missing tables

Revision ID: b1a2c3d4e5f7
Revises: 6f7a8b9c0d1e
Create Date: 2026-05-28 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b1a2c3d4e5f7"
down_revision: str | Sequence[str] | None = "6f7a8b9c0d1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add missing columns to pipeline_stage
    op.add_column(
        "pipeline_stage",
        sa.Column("evaluationEnabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "pipeline_stage",
        sa.Column("sheetEnabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "pipeline_stage",
        sa.Column("evaluationType", sa.String(32), nullable=True),
    )
    op.add_column(
        "pipeline_stage",
        sa.Column("evaluationIncludeTotal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "pipeline_stage",
        sa.Column("evaluationIncludeAnalysis", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Remove server_default after backfill so new explicit inserts don't inherit it
    op.alter_column("pipeline_stage", "evaluationEnabled", server_default=None)
    op.alter_column("pipeline_stage", "sheetEnabled", server_default=None)
    op.alter_column("pipeline_stage", "evaluationIncludeTotal", server_default=None)
    op.alter_column("pipeline_stage", "evaluationIncludeAnalysis", server_default=None)

    # Create stage_evaluation_category table
    op.create_table(
        "stage_evaluation_category",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organizationId", sa.String(36), nullable=False),
        sa.Column("stageId", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("valueType", sa.String(32), nullable=False, server_default="NUMERIC"),
        sa.Column("maxScore", sa.Integer(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stageId"], ["pipeline_stage.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("stageId", "order", name="uq_stage_evaluation_category_order"),
    )
    op.create_index(
        "ix_stage_evaluation_category_org_stage",
        "stage_evaluation_category",
        ["organizationId", "stageId"],
    )

    # Create stage_evaluation_workspace table
    op.create_table(
        "stage_evaluation_workspace",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organizationId", sa.String(36), nullable=False),
        sa.Column("stageId", sa.String(36), nullable=False),
        sa.Column("googleSpreadsheetId", sa.String(255), nullable=False),
        sa.Column("googleSpreadsheetUrl", sa.Text(), nullable=False),
        sa.Column("googleSheetId", sa.Integer(), nullable=True),
        sa.Column("googleSheetTitle", sa.String(100), nullable=False),
        sa.Column("createdByMemberId", sa.String(36), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stageId"], ["pipeline_stage.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["createdByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("stageId", name="uq_stage_evaluation_workspace_stage"),
        sa.UniqueConstraint("organizationId", "stageId", name="uq_stage_evaluation_workspace_org_stage"),
    )
    op.create_index(
        "ix_stage_evaluation_workspace_org_stage",
        "stage_evaluation_workspace",
        ["organizationId", "stageId"],
    )


def downgrade() -> None:
    op.drop_table("stage_evaluation_workspace")
    op.drop_table("stage_evaluation_category")
    op.drop_column("pipeline_stage", "evaluationIncludeAnalysis")
    op.drop_column("pipeline_stage", "evaluationIncludeTotal")
    op.drop_column("pipeline_stage", "evaluationType")
    op.drop_column("pipeline_stage", "sheetEnabled")
    op.drop_column("pipeline_stage", "evaluationEnabled")
