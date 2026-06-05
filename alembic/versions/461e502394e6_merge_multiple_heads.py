"""merge multiple heads

Revision ID: 461e502394e6
Revises: a2b3c4d5e6f7, cc3d0209aab6, e7f8a9b0c1d2
Create Date: 2026-06-05 15:26:37.167739
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '461e502394e6'
down_revision: Union[str, None] = ('a2b3c4d5e6f7', 'cc3d0209aab6', 'e7f8a9b0c1d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
