"""merge_all_heads

Revision ID: 4b262fe191ed
Revises: 40e3ade9ac5a, 4e906bd86ec5, 5f4aa7b8a682
Create Date: 2026-05-15 06:45:18.278336
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b262fe191ed'
down_revision: Union[str, None] = ('40e3ade9ac5a', '4e906bd86ec5', '5f4aa7b8a682')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
