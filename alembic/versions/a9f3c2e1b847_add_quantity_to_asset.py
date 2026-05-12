"""add_quantity_to_asset

Revision ID: a9f3c2e1b847
Revises: f43cf5b85a2b
Create Date: 2026-05-11 15:00:00.000000
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9f3c2e1b847"
down_revision: Union[str, None] = "f43cf5b85a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("asset", "quantity")
