"""add projects and job requisitions

Revision ID: f31c0d9b7a12
Revises: 8e4d8fe3b1a1
Create Date: 2026-05-07 14:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f31c0d9b7a12"
down_revision: Union[str, tuple[str, str], None] = "8e4d8fe3b1a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("clientName", sa.String(length=255), nullable=True),
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("budgetedHours", sa.Numeric(10, 2), nullable=True),
        sa.Column("startDate", sa.Date(), nullable=True),
        sa.Column("endDate", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("billable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deletedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("project_organizationId_idx", "project", ["organizationId"], unique=False)
    op.create_index("project_organizationId_status_idx", "project", ["organizationId", "status"], unique=False)
    op.create_index("project_organizationId_deletedAt_idx", "project", ["organizationId", "deletedAt"], unique=False)

    op.create_table(
        "project_member",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("projectId", sa.String(length=36), nullable=False),
        sa.Column("memberId", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("allocatedHours", sa.Numeric(10, 2), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["memberId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["projectId"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("projectId", "memberId", name="project_member_projectId_memberId_key"),
    )
    op.create_index("project_member_projectId_idx", "project_member", ["projectId"], unique=False)
    op.create_index("project_member_memberId_idx", "project_member", ["memberId"], unique=False)

    op.create_table(
        "project_task",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("projectId", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assignedMemberId", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="TODO", nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assignedMemberId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["projectId"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("project_task_projectId_idx", "project_task", ["projectId"], unique=False)
    op.create_index("project_task_assignedMemberId_idx", "project_task", ["assignedMemberId"], unique=False)
    op.create_index("project_task_projectId_status_idx", "project_task", ["projectId", "status"], unique=False)

    op.create_table(
        "job_requisition",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("departmentId", sa.String(length=36), nullable=True),
        sa.Column("hiringManagerId", sa.String(length=36), nullable=True),
        sa.Column("requiredSkills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False),
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("targetDate", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
        sa.Column("currentApprovalStep", sa.String(length=32), nullable=True),
        sa.Column("rejectionReason", sa.Text(), nullable=True),
        sa.Column("jobPostingUrl", sa.String(length=512), nullable=True),
        sa.Column("createdById", sa.String(length=36), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["createdById"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["departmentId"], ["department.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["hiringManagerId"], ["member.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("job_requisition_organizationId_idx", "job_requisition", ["organizationId"], unique=False)
    op.create_index("job_requisition_organizationId_status_idx", "job_requisition", ["organizationId", "status"], unique=False)
    op.create_index("job_requisition_departmentId_idx", "job_requisition", ["departmentId"], unique=False)
    op.create_index("job_requisition_hiringManagerId_idx", "job_requisition", ["hiringManagerId"], unique=False)

    op.create_table(
        "job_requisition_approval",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("requisitionId", sa.String(length=36), nullable=False),
        sa.Column("approverId", sa.String(length=36), nullable=False),
        sa.Column("step", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approverId"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requisitionId"], ["job_requisition.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("job_requisition_approval_requisitionId_idx", "job_requisition_approval", ["requisitionId"], unique=False)
    op.create_index("job_requisition_approval_approverId_idx", "job_requisition_approval", ["approverId"], unique=False)


def downgrade() -> None:
    op.drop_index("job_requisition_approval_approverId_idx", table_name="job_requisition_approval")
    op.drop_index("job_requisition_approval_requisitionId_idx", table_name="job_requisition_approval")
    op.drop_table("job_requisition_approval")

    op.drop_index("job_requisition_hiringManagerId_idx", table_name="job_requisition")
    op.drop_index("job_requisition_departmentId_idx", table_name="job_requisition")
    op.drop_index("job_requisition_organizationId_status_idx", table_name="job_requisition")
    op.drop_index("job_requisition_organizationId_idx", table_name="job_requisition")
    op.drop_table("job_requisition")

    op.drop_index("project_task_projectId_status_idx", table_name="project_task")
    op.drop_index("project_task_assignedMemberId_idx", table_name="project_task")
    op.drop_index("project_task_projectId_idx", table_name="project_task")
    op.drop_table("project_task")

    op.drop_index("project_member_memberId_idx", table_name="project_member")
    op.drop_index("project_member_projectId_idx", table_name="project_member")
    op.drop_table("project_member")

    op.drop_index("project_organizationId_deletedAt_idx", table_name="project")
    op.drop_index("project_organizationId_status_idx", table_name="project")
    op.drop_index("project_organizationId_idx", table_name="project")
    op.drop_table("project")
