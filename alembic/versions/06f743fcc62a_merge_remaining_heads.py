"""merge remaining heads

Revision ID: 06f743fcc62a
Revises: 7d9e5f3a1c6b, c3f4a5b6d7e8
Create Date: 2026-05-29 12:49:29.746876
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06f743fcc62a'
down_revision: Union[str, None] = ('7d9e5f3a1c6b', 'c3f4a5b6d7e8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
