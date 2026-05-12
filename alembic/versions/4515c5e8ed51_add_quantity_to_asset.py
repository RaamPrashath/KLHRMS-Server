"""add quantity to asset

Revision ID: 4515c5e8ed51
Revises: 8595c04b4dc1
Create Date: 2026-05-11 15:37:21.864823
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4515c5e8ed51'
down_revision: Union[str, None] = '8595c04b4dc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
