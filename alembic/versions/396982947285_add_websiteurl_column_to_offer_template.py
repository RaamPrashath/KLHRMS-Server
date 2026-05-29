"""add websiteUrl column to offer template

Revision ID: 396982947285
Revises: e5f6a7b8c9d0
Create Date: 2026-05-28 15:59:11.335423
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '396982947285'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('offer_template', sa.Column('websiteUrl', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('offer_template', 'websiteUrl')
