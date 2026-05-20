"""merge_all_remaining_heads

Revision ID: 70353a1155f8
Revises: 74d2f8313b1d, 8e7d5f3b2c1a, e1a2b3c4d5f6
Create Date: 2026-05-20 06:27:03.367264
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70353a1155f8'
down_revision: Union[str, None] = ('74d2f8313b1d', '8e7d5f3b2c1a', 'e1a2b3c4d5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
