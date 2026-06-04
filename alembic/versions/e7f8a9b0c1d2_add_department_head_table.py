"""add department_head table

Revision ID: e7f8a9b0c1d2
Revises: 9d505aa3efc3
Create Date: 2026-06-04 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = '9d505aa3efc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('departmentHead',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('departmentId', sa.String(length=36), nullable=False),
        sa.Column('memberId', sa.String(length=36), nullable=False),
        sa.Column('assignedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['departmentId'], ['department.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['memberId'], ['member.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('departmentId', 'memberId', name='departmentHead_departmentId_memberId_key'),
    )
    op.create_index('departmentHead_departmentId_idx', 'departmentHead', ['departmentId'])
    op.create_index('departmentHead_memberId_idx', 'departmentHead', ['memberId'])


def downgrade() -> None:
    op.drop_index('departmentHead_memberId_idx', table_name='departmentHead')
    op.drop_index('departmentHead_departmentId_idx', table_name='departmentHead')
    op.drop_table('departmentHead')
