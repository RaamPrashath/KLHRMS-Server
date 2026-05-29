"""add asset assignment handover tracking

Revision ID: b5f6c2e4a901
Revises: a91f4d2c6e11
Create Date: 2026-05-26 23:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b5f6c2e4a901"
down_revision: str | None = "a91f4d2c6e11"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_assignment",
        sa.Column("replacementAssignmentId", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "asset_assignment",
        sa.Column("handoverRequestedAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "asset_assignment",
        sa.Column("handoverCompletedAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "asset_assignment",
        sa.Column("handoverConditionNotes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "asset_assignment_replacementAssignmentId_fkey",
        "asset_assignment",
        "asset_assignment",
        ["replacementAssignmentId"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "asset_assignment_replacementAssignmentId_idx",
        "asset_assignment",
        ["replacementAssignmentId"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("asset_assignment_replacementAssignmentId_idx", table_name="asset_assignment")
    op.drop_constraint(
        "asset_assignment_replacementAssignmentId_fkey",
        "asset_assignment",
        type_="foreignkey",
    )
    op.drop_column("asset_assignment", "handoverConditionNotes")
    op.drop_column("asset_assignment", "handoverCompletedAt")
    op.drop_column("asset_assignment", "handoverRequestedAt")
    op.drop_column("asset_assignment", "replacementAssignmentId")
