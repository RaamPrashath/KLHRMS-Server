"""add_asset_code_to_category_definition

Revision ID: abcd1234e001
Revises: 983e5327cb8a
Create Date: 2026-05-14 16:12:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'abcd1234e001'
down_revision: Union[str, None] = '983e5327cb8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('asset_category_definition', sa.Column('asset_code', sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column('asset_category_definition', 'asset_code')
