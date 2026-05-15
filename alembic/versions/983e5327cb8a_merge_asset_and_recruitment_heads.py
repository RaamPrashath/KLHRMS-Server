"""merge_asset_and_recruitment_heads

Revision ID: 983e5327cb8a
Revises: 40e3ade9ac5a, a2b3c4d5e6f7, cd72a8217dc2
Create Date: 2026-05-14 16:08:24.400135
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '983e5327cb8a'
down_revision: Union[str, None] = ('40e3ade9ac5a', 'a2b3c4d5e6f7', 'cd72a8217dc2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
