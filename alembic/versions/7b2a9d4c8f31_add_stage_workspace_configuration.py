"""add stage workspace configuration

Revision ID: 7b2a9d4c8f31
Revises: 258a8b4eb1d5
Create Date: 2026-05-10 12:58:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b2a9d4c8f31"
down_revision: Union[str, None] = "258a8b4eb1d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_stage",
        sa.Column("meetingEnabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "pipeline_stage",
        sa.Column("offerLetterEnabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "pipeline_stage",
        sa.Column("evaluationEnabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("pipeline_stage", sa.Column("evaluationType", sa.String(length=32), nullable=True))
    op.add_column(
        "pipeline_stage",
        sa.Column("evaluationIncludeTotal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "pipeline_stage",
        sa.Column("evaluationIncludeAnalysis", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("pipeline_stage", sa.Column("dueDate", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "pipeline_stage",
        sa.Column("extendToNextWorkingDay", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "stage_evaluation_category",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("stageId", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stageId"], ["pipeline_stage.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stageId", "order", name="uq_stage_evaluation_category_order"),
    )
    op.create_index(
        "ix_stage_evaluation_category_org_stage",
        "stage_evaluation_category",
        ["organizationId", "stageId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stage_evaluation_category_organizationId"),
        "stage_evaluation_category",
        ["organizationId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stage_evaluation_category_stageId"),
        "stage_evaluation_category",
        ["stageId"],
        unique=False,
    )

    for column in (
        "meetingEnabled",
        "offerLetterEnabled",
        "evaluationEnabled",
        "evaluationIncludeTotal",
        "evaluationIncludeAnalysis",
        "extendToNextWorkingDay",
    ):
        op.alter_column("pipeline_stage", column, server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_stage_evaluation_category_stageId"), table_name="stage_evaluation_category")
    op.drop_index(op.f("ix_stage_evaluation_category_organizationId"), table_name="stage_evaluation_category")
    op.drop_index("ix_stage_evaluation_category_org_stage", table_name="stage_evaluation_category")
    op.drop_table("stage_evaluation_category")
    op.drop_column("pipeline_stage", "extendToNextWorkingDay")
    op.drop_column("pipeline_stage", "dueDate")
    op.drop_column("pipeline_stage", "evaluationIncludeAnalysis")
    op.drop_column("pipeline_stage", "evaluationIncludeTotal")
    op.drop_column("pipeline_stage", "evaluationType")
    op.drop_column("pipeline_stage", "evaluationEnabled")
    op.drop_column("pipeline_stage", "offerLetterEnabled")
    op.drop_column("pipeline_stage", "meetingEnabled")
