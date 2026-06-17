"""add archived_at to asset_maintenance_log

Revision ID: f3a7b8c9d0e1
Revises: e2840c1f6f2c
Create Date: 2026-06-17 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3a7b8c9d0e1"
down_revision: str | None = "e2840c1f6f2c"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_maintenance_log",
        sa.Column("archivedAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_asset_maintenance_log_archivedAt",
        "asset_maintenance_log",
        ["archivedAt"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_maintenance_log_archivedAt",
        table_name="asset_maintenance_log",
    )
    op.drop_column("asset_maintenance_log", "archivedAt")
