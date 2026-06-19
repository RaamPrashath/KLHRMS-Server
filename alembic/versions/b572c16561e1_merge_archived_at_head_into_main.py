"""merge archived_at head into main

Revision ID: b572c16561e1
Revises: c6d7e8f9a0b1, f3a7b8c9d0e1
Create Date: 2026-06-18 18:05:31.311926
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b572c16561e1'
down_revision: Union[str, None] = ('c6d7e8f9a0b1', 'f3a7b8c9d0e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
