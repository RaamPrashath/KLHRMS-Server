"""add quantity to asset

Revision ID: cd72a8217dc2
Revises: 4515c5e8ed51
Create Date: 2026-05-11 15:40:52.497139
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd72a8217dc2'
down_revision: Union[str, None] = '4515c5e8ed51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1")
    )


def downgrade() -> None:
    op.drop_column("asset", "quantity")
