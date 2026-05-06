"""add_timesheets

Revision ID: b7005c6c1bf0
Revises: e5b0768bcee0
Create Date: 2026-05-06 07:49:56.716899
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7005c6c1bf0'
down_revision: Union[str, None] = 'e5b0768bcee0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass