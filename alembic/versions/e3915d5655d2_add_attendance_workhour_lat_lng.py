"""add_attendance_workhour_lat_lng

Revision ID: e3915d5655d2
Revises: 7a17b0ce3f01
Create Date: 2026-05-04 17:07:07.069587
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e3915d5655d2'
down_revision: Union[str, None] = '7a17b0ce3f01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass