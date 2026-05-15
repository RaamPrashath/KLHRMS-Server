"""drop_pipeline_stage_order_unique_constraint

Revision ID: 4e906bd86ec5
Revises: a2b3c4d5e6f7
Create Date: 2026-05-14 17:11:28.376656
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e906bd86ec5'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
