"""add_entry_type_to_attendance_record

Revision ID: 37ad479eb5ed
Revises: 31b302d240b3
Create Date: 2026-06-10 17:00:19.501725
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37ad479eb5ed'
down_revision: Union[str, None] = '31b302d240b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attendanceRecord", sa.Column("entryType", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("attendanceRecord", "entryType")
