"""add_form_fields_and_custom_fields_jsonb

Revision ID: ab553a32e47b
Revises: c4c2d7c0ed3f
Create Date: 2026-06-15 14:04:27.516182
"""
from typing import Sequence, Union

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ab553a32e47b'
down_revision: Union[str, None] = 'c4c2d7c0ed3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_posting', sa.Column('formFields', postgresql.JSONB(), nullable=True))
    op.add_column('candidate_application', sa.Column('customFields', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('candidate_application', 'customFields')
    op.drop_column('job_posting', 'formFields')
