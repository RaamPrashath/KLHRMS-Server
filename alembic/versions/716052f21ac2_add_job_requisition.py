"""add_job_requisition

Revision ID: 716052f21ac2
Revises: f0a1b2c3d4e5
Create Date: 2026-05-14 11:30:06.712462
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '716052f21ac2'
down_revision: Union[str, None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass