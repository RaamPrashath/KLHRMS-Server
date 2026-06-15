"""add form_fields to job_requisition

Revision ID: e2840c1f6f2c
Revises: ab553a32e47b
Create Date: 2026-06-15 15:27:29.598493
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e2840c1f6f2c'
down_revision: Union[str, None] = 'ab553a32e47b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_requisition', sa.Column('formFields', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('job_requisition', 'formFields')
