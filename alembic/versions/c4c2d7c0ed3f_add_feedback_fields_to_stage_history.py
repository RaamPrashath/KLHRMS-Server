"""add_feedback_fields_to_stage_history

Revision ID: c4c2d7c0ed3f
Revises: cc3bf0181e86
Create Date: 2026-06-15 13:14:09.081955
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4c2d7c0ed3f'
down_revision: Union[str, None] = 'cc3bf0181e86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('application_stage_history', sa.Column('score', sa.Float(), nullable=True))
    op.add_column('application_stage_history', sa.Column('recommendation', sa.String(length=20), nullable=True))
    op.add_column('application_stage_history', sa.Column('strengths', sa.Text(), nullable=True))
    op.add_column('application_stage_history', sa.Column('areasOfImprovement', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('application_stage_history', 'areasOfImprovement')
    op.drop_column('application_stage_history', 'strengths')
    op.drop_column('application_stage_history', 'recommendation')
    op.drop_column('application_stage_history', 'score')
