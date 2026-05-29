"""add asset swap resolution fields

Revision ID: a91f4d2c6e11
Revises: 4c7a9d2e8f31
Create Date: 2026-05-26 21:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a91f4d2c6e11"
down_revision: str | None = "4c7a9d2e8f31"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_maintenance_log",
        sa.Column("estimatedDowntimeHours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "asset_maintenance_log",
        sa.Column("operationalCriticalityTier", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "asset_maintenance_log",
        sa.Column("replacementDecision", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "asset_maintenance_log",
        sa.Column("replacementAssetUnitId", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "asset_maintenance_log_replacementAssetUnitId_fkey",
        "asset_maintenance_log",
        "asset_unit",
        ["replacementAssetUnitId"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "asset_maintenance_log_replacementDecision_idx",
        "asset_maintenance_log",
        ["replacementDecision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("asset_maintenance_log_replacementDecision_idx", table_name="asset_maintenance_log")
    op.drop_constraint(
        "asset_maintenance_log_replacementAssetUnitId_fkey",
        "asset_maintenance_log",
        type_="foreignkey",
    )
    op.drop_column("asset_maintenance_log", "replacementAssetUnitId")
    op.drop_column("asset_maintenance_log", "replacementDecision")
    op.drop_column("asset_maintenance_log", "operationalCriticalityTier")
    op.drop_column("asset_maintenance_log", "estimatedDowntimeHours")
