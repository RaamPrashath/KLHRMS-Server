"""merge_heads

Revision ID: 9dda3254ec48
Revises: 0b40808410c8, 232c4c9e3cee
Create Date: 2026-05-05 12:46:51.990446
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dda3254ec48'
down_revision: Union[str, None] = ('0b40808410c8', '232c4c9e3cee')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
