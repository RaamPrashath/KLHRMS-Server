"""add_leave_holiday_timesheets

Revision ID: e5b0768bcee0
Revises: cdf11d509e0d
Create Date: 2026-05-06 07:48:14.065008
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5b0768bcee0'
down_revision: Union[str, None] = 'cdf11d509e0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop old leave/timesheet/reporting tables ─────────────────────────────
    op.drop_index(op.f('ix_leave_balances_employee_id'), table_name='leave_balances')
    op.drop_index(op.f('ix_leave_balances_leave_type_id'), table_name='leave_balances')
    op.drop_index(op.f('ix_leave_balances_organization_id'), table_name='leave_balances')
    op.drop_table('leave_balances')

    op.drop_index(op.f('ix_holidays_holiday_date'), table_name='holidays')
    op.drop_index(op.f('ix_holidays_organization_id'), table_name='holidays')
    op.drop_table('holidays')

    op.drop_index(op.f('ix_leave_requests_employee_id'), table_name='leave_requests')
    op.drop_index(op.f('ix_leave_requests_leave_type_id'), table_name='leave_requests')
    op.drop_index(op.f('ix_leave_requests_organization_id'), table_name='leave_requests')
    op.drop_table('leave_requests')

    op.drop_index(op.f('ix_leave_type_configs_organization_id'), table_name='leave_type_configs')
    op.drop_table('leave_type_configs')

    op.drop_index(op.f('ix_timesheet_entries_organization_id'), table_name='timesheet_entries')
    op.drop_index(op.f('ix_timesheet_entries_timesheet_id'), table_name='timesheet_entries')
    op.drop_table('timesheet_entries')

    op.drop_index(op.f('ix_timesheets_employee_id'), table_name='timesheets')
    op.drop_index(op.f('ix_timesheets_organization_id'), table_name='timesheets')
    op.drop_index(op.f('ix_timesheets_status'), table_name='timesheets')
    op.drop_table('timesheets')

    op.drop_index(op.f('ix_employee_reporting_employee_id'), table_name='employee_reporting')
    op.drop_index(op.f('ix_employee_reporting_manager_id'), table_name='employee_reporting')
    op.drop_index(op.f('ix_employee_reporting_organization_id'), table_name='employee_reporting')
    op.drop_table('employee_reporting')

    # ── Create new leave tables ───────────────────────────────────────────────
    op.create_table('holiday',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organizationId', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('holidayDate', sa.Date(), nullable=False),
        sa.Column('isRecurring', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.Column('deletedAt', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('holiday_organizationId_idx', 'holiday', ['organizationId'], unique=False)
    op.create_index('holiday_organizationId_holidayDate_idx', 'holiday', ['organizationId', 'holidayDate'], unique=False)
    op.create_index('holiday_organizationId_deletedAt_idx', 'holiday', ['organizationId', 'deletedAt'], unique=False)

    op.create_table('leave_type',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organizationId', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('quota', sa.Float(), nullable=False),
        sa.Column('carryForward', sa.Boolean(), nullable=False),
        sa.Column('isPaid', sa.Boolean(), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.Column('deletedAt', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organizationId', 'name', name='leave_type_organizationId_name_key')
    )
    op.create_index('leave_type_organizationId_idx', 'leave_type', ['organizationId'], unique=False)
    op.create_index('leave_type_organizationId_deletedAt_idx', 'leave_type', ['organizationId', 'deletedAt'], unique=False)

    op.create_table('leave_balance',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organizationId', sa.String(length=36), nullable=False),
        sa.Column('memberId', sa.String(length=36), nullable=False),
        sa.Column('leaveTypeId', sa.String(length=36), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('allocated', sa.Float(), nullable=False),
        sa.Column('used', sa.Float(), nullable=False),
        sa.Column('remaining', sa.Float(), nullable=False),
        sa.Column('carriedForward', sa.Float(), nullable=False),
        sa.Column('lapsed', sa.Float(), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.ForeignKeyConstraint(['leaveTypeId'], ['leave_type.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['memberId'], ['member.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organizationId', 'memberId', 'leaveTypeId', 'year', name='leave_balance_org_member_type_year_key')
    )
    op.create_index('leave_balance_organizationId_idx', 'leave_balance', ['organizationId'], unique=False)
    op.create_index('leave_balance_organizationId_memberId_year_idx', 'leave_balance', ['organizationId', 'memberId', 'year'], unique=False)
    op.create_index('leave_balance_organizationId_leaveTypeId_year_idx', 'leave_balance', ['organizationId', 'leaveTypeId', 'year'], unique=False)

    op.create_table('leave_request',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organizationId', sa.String(length=36), nullable=False),
        sa.Column('memberId', sa.String(length=36), nullable=False),
        sa.Column('leaveTypeId', sa.String(length=36), nullable=False),
        sa.Column('startDate', sa.Date(), nullable=False),
        sa.Column('endDate', sa.Date(), nullable=False),
        sa.Column('days', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('approvedById', sa.String(length=36), nullable=True),
        sa.Column('approverComment', sa.Text(), nullable=True),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.Column('cancelledAt', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deletedAt', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['approvedById'], ['member.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['leaveTypeId'], ['leave_type.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['memberId'], ['member.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('leave_request_organizationId_idx', 'leave_request', ['organizationId'], unique=False)
    op.create_index('leave_request_organizationId_memberId_idx', 'leave_request', ['organizationId', 'memberId'], unique=False)
    op.create_index('leave_request_organizationId_status_idx', 'leave_request', ['organizationId', 'status'], unique=False)
    op.create_index('leave_request_organizationId_leaveTypeId_idx', 'leave_request', ['organizationId', 'leaveTypeId'], unique=False)
    op.create_index('leave_request_organizationId_startDate_idx', 'leave_request', ['organizationId', 'startDate'], unique=False)
    op.create_index('leave_request_organizationId_startDate_endDate_idx', 'leave_request', ['organizationId', 'startDate', 'endDate'], unique=False)
    op.create_index('leave_request_approvedById_idx', 'leave_request', ['approvedById'], unique=False)

    # ── Add missing column ────────────────────────────────────────────────────
    op.add_column('weekly_plans', sa.Column('project', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('weekly_plans', 'project')

    op.drop_index('leave_request_approvedById_idx', table_name='leave_request')
    op.drop_index('leave_request_organizationId_startDate_endDate_idx', table_name='leave_request')
    op.drop_index('leave_request_organizationId_startDate_idx', table_name='leave_request')
    op.drop_index('leave_request_organizationId_leaveTypeId_idx', table_name='leave_request')
    op.drop_index('leave_request_organizationId_status_idx', table_name='leave_request')
    op.drop_index('leave_request_organizationId_memberId_idx', table_name='leave_request')
    op.drop_index('leave_request_organizationId_idx', table_name='leave_request')
    op.drop_table('leave_request')

    op.drop_index('leave_balance_organizationId_leaveTypeId_year_idx', table_name='leave_balance')
    op.drop_index('leave_balance_organizationId_memberId_year_idx', table_name='leave_balance')
    op.drop_index('leave_balance_organizationId_idx', table_name='leave_balance')
    op.drop_table('leave_balance')

    op.drop_index('leave_type_organizationId_deletedAt_idx', table_name='leave_type')
    op.drop_index('leave_type_organizationId_idx', table_name='leave_type')
    op.drop_table('leave_type')

    op.drop_index('holiday_organizationId_deletedAt_idx', table_name='holiday')
    op.drop_index('holiday_organizationId_holidayDate_idx', table_name='holiday')
    op.drop_index('holiday_organizationId_idx', table_name='holiday')
    op.drop_table('holiday')