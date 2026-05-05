"""add_leave_weekly_plan

Revision ID: cdf11d509e0d
Revises: 9dda3254ec48
Create Date: 2026-05-05 12:47:05.338807
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'cdf11d509e0d'
down_revision: Union[str, None] = '9dda3254ec48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('employee_reporting',
        sa.Column('employee_id', sa.String(length=255), nullable=False),
        sa.Column('manager_id', sa.String(length=255), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_employee_reporting_employee_id'), 'employee_reporting', ['employee_id'], unique=True)
    op.create_index(op.f('ix_employee_reporting_manager_id'), 'employee_reporting', ['manager_id'], unique=False)
    op.create_index(op.f('ix_employee_reporting_organization_id'), 'employee_reporting', ['organization_id'], unique=False)

    op.create_table('holidays',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('is_recurring', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_holidays_holiday_date'), 'holidays', ['holiday_date'], unique=False)
    op.create_index(op.f('ix_holidays_organization_id'), 'holidays', ['organization_id'], unique=False)

    op.create_table('leave_type_configs',
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('quota', sa.Float(), nullable=False),
        sa.Column('carry_forward', sa.Boolean(), nullable=False),
        sa.Column('is_paid', sa.Boolean(), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leave_type_configs_organization_id'), 'leave_type_configs', ['organization_id'], unique=False)

    op.create_table('weekly_plans',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('work_location', sa.String(length=20), nullable=False),
        sa.Column('project', sa.String(length=200), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', 'date', name='uq_weekly_plan_org_user_date')
    )
    op.create_index(op.f('ix_weekly_plans_organization_id'), 'weekly_plans', ['organization_id'], unique=False)
    op.create_index(op.f('ix_weekly_plans_user_id'), 'weekly_plans', ['user_id'], unique=False)

    op.create_table('leave_balances',
        sa.Column('employee_id', sa.String(length=255), nullable=False),
        sa.Column('leave_type_id', sa.UUID(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('allocated', sa.Float(), nullable=False),
        sa.Column('used', sa.Float(), nullable=False),
        sa.Column('remaining', sa.Float(), nullable=False),
        sa.Column('carried_forward', sa.Float(), nullable=False),
        sa.Column('lapsed', sa.Float(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['leave_type_id'], ['leave_type_configs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'employee_id', 'leave_type_id', 'year', name='uq_leave_balance_org_emp_type_year')
    )
    op.create_index(op.f('ix_leave_balances_employee_id'), 'leave_balances', ['employee_id'], unique=False)
    op.create_index(op.f('ix_leave_balances_leave_type_id'), 'leave_balances', ['leave_type_id'], unique=False)
    op.create_index(op.f('ix_leave_balances_organization_id'), 'leave_balances', ['organization_id'], unique=False)

    op.create_table('leave_requests',
        sa.Column('employee_id', sa.String(length=255), nullable=False),
        sa.Column('leave_type_id', sa.UUID(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('days', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('approved_by_id', sa.String(length=255), nullable=True),
        sa.Column('approver_comment', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('createdAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updatedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['leave_type_id'], ['leave_type_configs.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leave_requests_employee_id'), 'leave_requests', ['employee_id'], unique=False)
    op.create_index(op.f('ix_leave_requests_leave_type_id'), 'leave_requests', ['leave_type_id'], unique=False)
    op.create_index(op.f('ix_leave_requests_organization_id'), 'leave_requests', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_leave_requests_organization_id'), table_name='leave_requests')
    op.drop_index(op.f('ix_leave_requests_leave_type_id'), table_name='leave_requests')
    op.drop_index(op.f('ix_leave_requests_employee_id'), table_name='leave_requests')
    op.drop_table('leave_requests')
    op.drop_index(op.f('ix_leave_balances_organization_id'), table_name='leave_balances')
    op.drop_index(op.f('ix_leave_balances_leave_type_id'), table_name='leave_balances')
    op.drop_index(op.f('ix_leave_balances_employee_id'), table_name='leave_balances')
    op.drop_table('leave_balances')
    op.drop_index(op.f('ix_weekly_plans_user_id'), table_name='weekly_plans')
    op.drop_index(op.f('ix_weekly_plans_organization_id'), table_name='weekly_plans')
    op.drop_table('weekly_plans')
    op.drop_index(op.f('ix_leave_type_configs_organization_id'), table_name='leave_type_configs')
    op.drop_table('leave_type_configs')
    op.drop_index(op.f('ix_holidays_organization_id'), table_name='holidays')
    op.drop_index(op.f('ix_holidays_holiday_date'), table_name='holidays')
    op.drop_table('holidays')
    op.drop_index(op.f('ix_employee_reporting_organization_id'), table_name='employee_reporting')
    op.drop_index(op.f('ix_employee_reporting_manager_id'), table_name='employee_reporting')
    op.drop_index(op.f('ix_employee_reporting_employee_id'), table_name='employee_reporting')
    op.drop_table('employee_reporting')