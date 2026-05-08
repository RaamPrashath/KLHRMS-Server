"""add_public_holiday_master

Revision ID: 6c55e6750bb9
Revises: 8e4d8fe3b1a1
Create Date: 2026-05-07 08:00:14.213222
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '6c55e6750bb9'
down_revision: Union[str, None] = '8e4d8fe3b1a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add public_holiday_master table
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

    # Drop old project tables
    op.drop_index(op.f('ix_project_members_org_employee_active'), table_name='project_members')
    op.drop_index(op.f('ix_project_members_project_active'), table_name='project_members')
    op.drop_table('project_members')
    op.drop_index(op.f('ix_projects_org_department'), table_name='projects')
    op.drop_index(op.f('ix_projects_org_manager'), table_name='projects')
    op.drop_index(op.f('ix_projects_org_status'), table_name='projects')
    op.drop_index(op.f('ix_projects_organization_id'), table_name='projects')
    op.drop_table('projects')

    # Drop department.description column
    op.drop_column('department', 'description')

    # Add holiday.isHoliday column
    op.add_column('holiday', sa.Column('isHoliday', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('holiday', 'isHoliday')
    op.add_column('department', sa.Column('description', sa.Text(), nullable=True))
    op.drop_index('public_holiday_master_year_location_idx', table_name='public_holiday_master')
    op.drop_table('public_holiday_master')