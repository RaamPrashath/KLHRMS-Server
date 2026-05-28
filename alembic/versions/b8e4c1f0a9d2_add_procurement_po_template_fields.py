"""add_procurement_po_template_fields

Revision ID: b8e4c1f0a9d2
Revises: f0e1d2c3b4a5
Create Date: 2026-05-28 14:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e4c1f0a9d2"
down_revision: Union[str, None] = "f0e1d2c3b4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset_purchase_order",
        sa.Column("templateVersion", sa.String(length=64), nullable=False, server_default="v1"),
    )
    op.add_column(
        "asset_purchase_order",
        sa.Column("templateData", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )


def downgrade() -> None:
    op.drop_column("asset_purchase_order", "templateData")
    op.drop_column("asset_purchase_order", "templateVersion")
