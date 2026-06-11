"""merge_heads

Revision ID: 31b302d240b3
Revises: bb12cc34dd56, e6f7a8b9c0d2
Create Date: 2026-06-10 17:00:14.568467
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31b302d240b3'
down_revision: Union[str, None] = ('bb12cc34dd56', 'e6f7a8b9c0d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
