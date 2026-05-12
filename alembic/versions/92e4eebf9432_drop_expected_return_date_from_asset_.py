"""drop_expected_return_date_from_asset_assignment

Revision ID: 92e4eebf9432
Revises: 12be30a4e06c
Create Date: 2026-05-11 14:00:00.000000
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "92e4eebf9432"
down_revision: Union[str, None] = "12be30a4e06c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the index first, then the column
    op.drop_index("asset_assignment_expectedReturnDate_idx", table_name="asset_assignment")
    op.drop_column("asset_assignment", "expectedReturnDate")


def downgrade() -> None:
    op.add_column(
        "asset_assignment",
        sa.Column("expectedReturnDate", sa.Date(), nullable=True),
    )
    op.create_index(
        "asset_assignment_expectedReturnDate_idx",
        "asset_assignment",
        ["expectedReturnDate"],
        unique=False,
    )
