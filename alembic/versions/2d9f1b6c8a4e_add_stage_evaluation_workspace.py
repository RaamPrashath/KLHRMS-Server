"""add stage evaluation workspace

Revision ID: 2d9f1b6c8a4e
Revises: 7b2a9d4c8f31
Create Date: 2026-05-10 15:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d9f1b6c8a4e"
down_revision: Union[str, None] = "7b2a9d4c8f31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stage_evaluation_workspace",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("stageId", sa.String(length=36), nullable=False),
        sa.Column("googleSpreadsheetId", sa.String(length=255), nullable=False),
        sa.Column("googleSpreadsheetUrl", sa.Text(), nullable=False),
        sa.Column("googleSheetId", sa.Integer(), nullable=True),
        sa.Column("googleSheetTitle", sa.String(length=100), nullable=False),
        sa.Column("createdByMemberId", sa.String(length=36), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["createdByMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stageId"], ["pipeline_stage.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stageId", name="uq_stage_evaluation_workspace_stage"),
        sa.UniqueConstraint(
            "organizationId",
            "stageId",
            name="uq_stage_evaluation_workspace_org_stage",
        ),
    )
    op.create_index(
        "ix_stage_evaluation_workspace_org_stage",
        "stage_evaluation_workspace",
        ["organizationId", "stageId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stage_evaluation_workspace_createdByMemberId"),
        "stage_evaluation_workspace",
        ["createdByMemberId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stage_evaluation_workspace_organizationId"),
        "stage_evaluation_workspace",
        ["organizationId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stage_evaluation_workspace_stageId"),
        "stage_evaluation_workspace",
        ["stageId"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stage_evaluation_workspace_stageId"), table_name="stage_evaluation_workspace")
    op.drop_index(op.f("ix_stage_evaluation_workspace_organizationId"), table_name="stage_evaluation_workspace")
    op.drop_index(op.f("ix_stage_evaluation_workspace_createdByMemberId"), table_name="stage_evaluation_workspace")
    op.drop_index("ix_stage_evaluation_workspace_org_stage", table_name="stage_evaluation_workspace")
    op.drop_table("stage_evaluation_workspace")
