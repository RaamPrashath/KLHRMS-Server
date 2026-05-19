"""add requisition new fields and activity log

Revision ID: c9d4e2a7f501
Revises: b8f2d6a41c90, fa7c2d1e9b44
Create Date: 2026-05-17 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9d4e2a7f501"
down_revision: str | tuple[str, str] | None = ("b8f2d6a41c90", "fa7c2d1e9b44")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_REQUISITION_STATUSES = (
    "PENDING_APPROVAL",
    "PARTIALLY_APPROVED",
    "PUBLISHED",
    "ACTIVE_HIRING",
    "FILLED",
    "ARCHIVED",
)

OLD_REQUISITION_STATUSES = (
    "DRAFT",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "CLOSED",
)


def upgrade() -> None:
    for status in NEW_REQUISITION_STATUSES:
        op.execute(f"ALTER TYPE jobrequisitionstatus ADD VALUE IF NOT EXISTS '{status}'")

    op.add_column("job_requisition", sa.Column("hiringReason", sa.String(), nullable=True))
    op.add_column(
        "job_requisition",
        sa.Column("priority", sa.String(), server_default="MEDIUM", nullable=False),
    )
    op.add_column(
        "job_requisition",
        sa.Column("replacementForId", sa.String(length=36), nullable=True),
    )
    op.add_column("job_requisition", sa.Column("businessJustification", sa.Text(), nullable=True))
    op.add_column(
        "job_requisition",
        sa.Column(
            "salaryVisibility",
            sa.String(),
            server_default="INTERNAL_ONLY",
            nullable=False,
        ),
    )
    op.add_column("job_requisition", sa.Column("experienceLevel", sa.String(), nullable=True))
    op.add_column("job_requisition", sa.Column("minExperience", sa.Integer(), nullable=True))
    op.add_column("job_requisition", sa.Column("education", sa.String(), nullable=True))
    op.add_column(
        "job_requisition",
        sa.Column("certifications", sa.ARRAY(sa.String()), nullable=True),
    )
    op.add_column("job_requisition", sa.Column("roleSummary", sa.Text(), nullable=True))
    op.add_column("job_requisition", sa.Column("responsibilities", sa.Text(), nullable=True))
    op.add_column("job_requisition", sa.Column("requirementsRich", sa.Text(), nullable=True))
    op.add_column("job_requisition", sa.Column("benefits", sa.Text(), nullable=True))
    op.add_column("job_requisition", sa.Column("aboutTeam", sa.Text(), nullable=True))
    op.add_column("job_requisition", sa.Column("requisitionNumber", sa.Integer(), nullable=True))
    op.alter_column("job_requisition", "priority", server_default=None)
    op.alter_column("job_requisition", "salaryVisibility", server_default=None)
    op.create_index(
        op.f("ix_job_requisition_replacementForId"),
        "job_requisition",
        ["replacementForId"],
        unique=False,
    )
    op.create_index(
        "ix_job_requisition_org_replacement",
        "job_requisition",
        ["organizationId", "replacementForId"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("job_requisition_replacementForId_fkey"),
        "job_requisition",
        "member",
        ["replacementForId"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "requisition_activity_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizationId", sa.String(length=36), nullable=False),
        sa.Column("requisitionId", sa.String(length=36), nullable=False),
        sa.Column("actorId", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("fieldChanges", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actorId"], ["member.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organizationId"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requisitionId"], ["job_requisition.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_requisition_activity_log_action"),
        "requisition_activity_log",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_requisition_activity_log_actorId"),
        "requisition_activity_log",
        ["actorId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_requisition_activity_log_createdAt"),
        "requisition_activity_log",
        ["createdAt"],
        unique=False,
    )
    op.create_index(
        "ix_requisition_activity_log_org_action",
        "requisition_activity_log",
        ["organizationId", "action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_requisition_activity_log_organizationId"),
        "requisition_activity_log",
        ["organizationId"],
        unique=False,
    )
    op.create_index(
        op.f("ix_requisition_activity_log_requisitionId"),
        "requisition_activity_log",
        ["requisitionId"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_requisition_activity_log_requisitionId"),
        table_name="requisition_activity_log",
    )
    op.drop_index(
        op.f("ix_requisition_activity_log_organizationId"),
        table_name="requisition_activity_log",
    )
    op.drop_index("ix_requisition_activity_log_org_action", table_name="requisition_activity_log")
    op.drop_index(
        op.f("ix_requisition_activity_log_createdAt"),
        table_name="requisition_activity_log",
    )
    op.drop_index(
        op.f("ix_requisition_activity_log_actorId"),
        table_name="requisition_activity_log",
    )
    op.drop_index(op.f("ix_requisition_activity_log_action"), table_name="requisition_activity_log")
    op.drop_table("requisition_activity_log")

    op.drop_constraint(
        op.f("job_requisition_replacementForId_fkey"),
        "job_requisition",
        type_="foreignkey",
    )
    op.drop_index("ix_job_requisition_org_replacement", table_name="job_requisition")
    op.drop_index(op.f("ix_job_requisition_replacementForId"), table_name="job_requisition")
    op.drop_column("job_requisition", "requisitionNumber")
    op.drop_column("job_requisition", "aboutTeam")
    op.drop_column("job_requisition", "benefits")
    op.drop_column("job_requisition", "requirementsRich")
    op.drop_column("job_requisition", "responsibilities")
    op.drop_column("job_requisition", "roleSummary")
    op.drop_column("job_requisition", "certifications")
    op.drop_column("job_requisition", "education")
    op.drop_column("job_requisition", "minExperience")
    op.drop_column("job_requisition", "experienceLevel")
    op.drop_column("job_requisition", "salaryVisibility")
    op.drop_column("job_requisition", "businessJustification")
    op.drop_column("job_requisition", "replacementForId")
    op.drop_column("job_requisition", "priority")
    op.drop_column("job_requisition", "hiringReason")

    new_statuses = ", ".join(f"'{status}'" for status in NEW_REQUISITION_STATUSES)
    old_statuses = ", ".join(f"'{status}'" for status in OLD_REQUISITION_STATUSES)
    op.execute(
        f"""
        UPDATE job_requisition
        SET status = 'PENDING'
        WHERE status::text IN ({new_statuses})
        """
    )
    op.execute("ALTER TABLE job_requisition ALTER COLUMN status TYPE TEXT USING status::text")
    op.execute("DROP TYPE jobrequisitionstatus")
    op.execute(f"CREATE TYPE jobrequisitionstatus AS ENUM ({old_statuses})")
    op.execute(
        """
        ALTER TABLE job_requisition
        ALTER COLUMN status TYPE jobrequisitionstatus
        USING status::jobrequisitionstatus
        """
    )
