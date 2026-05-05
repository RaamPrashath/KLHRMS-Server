"""add_title_to_attendance_work_log

Revision ID: 232c4c9e3cee
Revises: cc76d8d8dace
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '232c4c9e3cee'
down_revision: Union[str, None] = 'cc76d8d8dace'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'attendanceWorkLog',
        sa.Column('title', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('attendanceWorkLog', 'title')
