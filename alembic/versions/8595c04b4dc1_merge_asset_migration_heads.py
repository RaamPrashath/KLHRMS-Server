"""merge asset migration heads

Revision ID: 8595c04b4dc1
Revises: 58d4b9ca0d21, a9f3c2e1b847
Create Date: 2026-05-11 15:37:14.467790
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8595c04b4dc1'
down_revision: Union[str, None] = ('58d4b9ca0d21', 'a9f3c2e1b847')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset",
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
            server_default="1"
        )
    )


def downgrade() -> None:
    op.drop_column("asset", "quantity")
