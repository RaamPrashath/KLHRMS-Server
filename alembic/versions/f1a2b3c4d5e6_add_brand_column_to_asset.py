"""add brand column to asset

Revision ID: f1a2b3c4d5e6
Revises: 4c7a9d2e8f31
Create Date: 2026-06-04 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "4c7a9d2e8f31"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset",
        sa.Column("brand", sa.String(length=120), nullable=True),
    )
    op.create_index(
        "asset_organizationId_brand_idx",
        "asset",
        ["organizationId", "brand"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("asset_organizationId_brand_idx", table_name="asset")
    op.drop_column("asset", "brand")
