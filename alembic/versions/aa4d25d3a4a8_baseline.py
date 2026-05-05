"""baseline

Revision ID: aa4d25d3a4a8
Revises: 
Create Date: 2026-04-30 15:52:50.948859
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa4d25d3a4a8'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    pass

def downgrade():
    pass