"""add_project_task_to_work_log

Revision ID: 5f4aa7b8a682
Revises: d1e2f3a4b5c6
Create Date: 2026-05-12 13:50:37.539296
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5f4aa7b8a682'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add projectId and projectTaskId columns to attendanceWorkLog
    op.add_column('attendanceWorkLog', sa.Column('projectId', sa.String(length=36), nullable=True))
    op.add_column('attendanceWorkLog', sa.Column('projectTaskId', sa.String(length=36), nullable=True))
    
    # Create indexes for better query performance
    op.create_index('attendanceWorkLog_projectId_idx', 'attendanceWorkLog', ['projectId'], unique=False)
    op.create_index('attendanceWorkLog_projectTaskId_idx', 'attendanceWorkLog', ['projectTaskId'], unique=False)


def downgrade() -> None:
    # Remove indexes
    op.drop_index('attendanceWorkLog_projectTaskId_idx', table_name='attendanceWorkLog')
    op.drop_index('attendanceWorkLog_projectId_idx', table_name='attendanceWorkLog')
    
    # Remove columns
    op.drop_column('attendanceWorkLog', 'projectTaskId')
    op.drop_column('attendanceWorkLog', 'projectId')
