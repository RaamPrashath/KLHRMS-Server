"""missing external migration

Revision ID: 5f4aa7b8a682
Revises: 39d16f2699f3
Create Date: 2026-05-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '5f4aa7b8a682'
down_revision: Union[str, None] = '39d16f2699f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass