"""merge migration heads

Revision ID: 6cbb91c6dd1f
Revises: 6f2d4b7c9a11, 719a71a8fb80
Create Date: 2026-05-11 12:42:07.268456
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cbb91c6dd1f'
down_revision: Union[str, None] = ('6f2d4b7c9a11', '719a71a8fb80')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
