"""add_attendance_work_log

Revision ID: cc76d8d8dace
Revises: e3915d5655d2
Create Date: 2026-05-05 07:16:22.603895
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'cc76d8d8dace'
down_revision: Union[str, None] = 'e3915d5655d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass