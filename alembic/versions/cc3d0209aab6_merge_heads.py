"""merge heads

Revision ID: cc3d0209aab6
Revises: 05aedd93e08d, f1a2b3c4d5e6
Create Date: 2026-06-04 20:16:10.261412
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc3d0209aab6'
down_revision: Union[str, None] = ('05aedd93e08d', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
