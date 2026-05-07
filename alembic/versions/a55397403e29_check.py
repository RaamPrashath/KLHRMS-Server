"""check

Revision ID: a55397403e29
Revises: a1b2c3d4e5f6
Create Date: 2026-05-07 13:04:34.718515
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a55397403e29'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create public_holiday_master
    op.create_table('public_holiday_master',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('location', sa.String(length=50), server_default='IN-TN', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'name', 'location', name='public_holiday_master_date_name_location_key')
    )
    op.create_index('public_holiday_master_year_location_idx', 'public_holiday_master', ['year', 'location'], unique=False)

    # Drop orphaned project/job tables
    op.drop_index(op.f('project_task_assignedMemberId_idx'), table_name='project_task')
    op.drop_index(op.f('project_task_projectId_idx'), table_name='project_task')
    op.drop_index(op.f('project_task_projectId_status_idx'), table_name='project_task')
    op.drop_table('project_task')

    op.drop_index(op.f('project_member_memberId_idx'), table_name='project_member')
    op.drop_index(op.f('project_member_projectId_idx'), table_name='project_member')
    op.drop_table('project_member')

    op.drop_index(op.f('project_organizationId_deletedAt_idx'), table_name='project')
    op.drop_index(op.f('project_organizationId_idx'), table_name='project')
    op.drop_index(op.f('project_organizationId_status_idx'), table_name='project')
    op.drop_table('project')

    op.drop_index(op.f('job_requisition_approval_approverId_idx'), table_name='job_requisition_approval')
    op.drop_index(op.f('job_requisition_approval_requisitionId_idx'), table_name='job_requisition_approval')
    op.drop_table('job_requisition_approval')

    op.drop_index(op.f('job_requisition_departmentId_idx'), table_name='job_requisition')
    op.drop_index(op.f('job_requisition_hiringManagerId_idx'), table_name='job_requisition')
    op.drop_index(op.f('job_requisition_organizationId_idx'), table_name='job_requisition')
    op.drop_index(op.f('job_requisition_organizationId_status_idx'), table_name='job_requisition')
    op.drop_table('job_requisition')

    # Add holiday.isHoliday
    op.add_column('holiday', sa.Column('isHoliday', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('holiday', 'isHoliday')
    op.drop_index('public_holiday_master_year_location_idx', table_name='public_holiday_master')
    op.drop_table('public_holiday_master')