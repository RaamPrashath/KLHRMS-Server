"""merge_heads_add_formfields_to_posting

Revision ID: d151fe9ddc14
Revises: e2840c1f6f2c, m001_merge_heads
Create Date: 2026-06-16 13:14:30.753114
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd151fe9ddc14'
down_revision: Union[str, None] = ('e2840c1f6f2c', 'm001_merge_heads')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
