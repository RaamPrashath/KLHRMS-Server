"""repair job requisition schema drift

Revision ID: f6a7b8c9d012
Revises: 9bc8279279dd
Create Date: 2026-05-20 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f6a7b8c9d012"
down_revision: str | Sequence[str] | None = "9bc8279279dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for status in (
        "PENDING_APPROVAL",
        "PARTIALLY_APPROVED",
        "PUBLISHED",
        "ACTIVE_HIRING",
        "FILLED",
        "ARCHIVED",
    ):
        op.execute(f"ALTER TYPE jobrequisitionstatus ADD VALUE IF NOT EXISTS '{status}'")

    op.execute(
        """
        ALTER TABLE job_requisition
            ADD COLUMN IF NOT EXISTS "hiringReason" TEXT,
            ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'MEDIUM',
            ADD COLUMN IF NOT EXISTS "replacementForId" VARCHAR(36),
            ADD COLUMN IF NOT EXISTS "businessJustification" TEXT,
            ADD COLUMN IF NOT EXISTS "salaryVisibility" TEXT NOT NULL DEFAULT 'INTERNAL_ONLY',
            ADD COLUMN IF NOT EXISTS "experienceLevel" TEXT,
            ADD COLUMN IF NOT EXISTS "minExperience" INTEGER,
            ADD COLUMN IF NOT EXISTS education TEXT,
            ADD COLUMN IF NOT EXISTS certifications TEXT[],
            ADD COLUMN IF NOT EXISTS "roleSummary" TEXT,
            ADD COLUMN IF NOT EXISTS responsibilities TEXT,
            ADD COLUMN IF NOT EXISTS "requirementsRich" TEXT,
            ADD COLUMN IF NOT EXISTS benefits TEXT,
            ADD COLUMN IF NOT EXISTS "aboutTeam" TEXT,
            ADD COLUMN IF NOT EXISTS "requisitionNumber" INTEGER
        """
    )
    op.execute("ALTER TABLE job_requisition ALTER COLUMN priority DROP DEFAULT")
    op.execute("ALTER TABLE job_requisition ALTER COLUMN \"salaryVisibility\" DROP DEFAULT")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_job_requisition_replacementForId"
        ON job_requisition ("replacementForId")
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_job_requisition_org_replacement
        ON job_requisition ("organizationId", "replacementForId")
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'job_requisition_replacementForId_fkey'
            ) THEN
                ALTER TABLE job_requisition
                    ADD CONSTRAINT "job_requisition_replacementForId_fkey"
                    FOREIGN KEY ("replacementForId")
                    REFERENCES member (id)
                    ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS requisition_activity_log (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "requisitionId" VARCHAR(36) NOT NULL REFERENCES job_requisition(id) ON DELETE CASCADE,
            "actorId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            action VARCHAR(50) NOT NULL,
            "fieldChanges" JSON,
            comment TEXT,
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_requisition_activity_log_action"
        ON requisition_activity_log (action)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_requisition_activity_log_actorId"
        ON requisition_activity_log ("actorId")
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_requisition_activity_log_createdAt"
        ON requisition_activity_log ("createdAt")
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_requisition_activity_log_org_action
        ON requisition_activity_log ("organizationId", action)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_requisition_activity_log_organizationId"
        ON requisition_activity_log ("organizationId")
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS "ix_requisition_activity_log_requisitionId"
        ON requisition_activity_log ("requisitionId")
        """
    )


def downgrade() -> None:
    pass
