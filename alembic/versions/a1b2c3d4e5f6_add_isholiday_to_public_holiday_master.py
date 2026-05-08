"""add_isholiday_to_public_holiday_master

Revision ID: a1b2c3d4e5f6
Revises: 6c55e6750bb9
Create Date: 2026-05-07 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "6c55e6750bb9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass