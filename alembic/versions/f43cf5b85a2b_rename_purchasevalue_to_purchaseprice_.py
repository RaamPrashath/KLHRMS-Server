"""rename_purchaseValue_to_purchasePrice_on_asset

Revision ID: f43cf5b85a2b
Revises: 92e4eebf9432
Create Date: 2026-05-11 14:10:00.000000
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "f43cf5b85a2b"
down_revision: Union[str, None] = "92e4eebf9432"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("asset", "purchaseValue", new_column_name="purchasePrice")


def downgrade() -> None:
    op.alter_column("asset", "purchasePrice", new_column_name="purchaseValue")
