"""merge_orphaned_a7b9c1d3e5f7

Revision ID: cc3bf0181e86
Revises: a7b9c1d3e5f7, 1cff6f7e415e
Create Date: 2026-06-15 13:13:02.637818
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc3bf0181e86'
down_revision: Union[str, None] = ('a7b9c1d3e5f7', '1cff6f7e415e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
