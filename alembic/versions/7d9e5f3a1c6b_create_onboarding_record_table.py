"""create onboarding_record table

Revision ID: 7d9e5f3a1c6b
Revises: a3f5e7c9b1d0
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "7d9e5f3a1c6b"
down_revision: str | Sequence[str] | None = "a3f5e7c9b1d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'onboardingstatus') THEN
                CREATE TYPE onboardingstatus AS ENUM ('PENDING', 'DOCUMENTS_SUBMITTED', 'CREDENTIALS_SENT');
            END IF;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_record (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "applicationId" VARCHAR(36) NOT NULL REFERENCES candidate_application(id) ON DELETE CASCADE,
            "candidateToken" VARCHAR NOT NULL UNIQUE,
            status onboardingstatus NOT NULL DEFAULT 'PENDING',
            "aadharUrl" TEXT,
            "aadharBucket" VARCHAR(120),
            "aadharStoragePath" TEXT,
            "panUrl" TEXT,
            "panBucket" VARCHAR(120),
            "panStoragePath" TEXT,
            "assignedRoleId" VARCHAR(36) REFERENCES role(id) ON DELETE SET NULL,
            "assignedEmail" VARCHAR(320),
            "tokenSentAt" TIMESTAMP WITH TIME ZONE,
            "submittedAt" TIMESTAMP WITH TIME ZONE,
            "credentialsSentAt" TIMESTAMP WITH TIME ZONE,
            "credentialsEmailError" TEXT,
            "createdAt" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            "updatedAt" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_onboarding_record_organization_id
        ON onboarding_record ("organizationId");
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_onboarding_record_application_id
        ON onboarding_record ("applicationId");
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS onboarding_record CASCADE;")
    op.execute("DROP TYPE IF EXISTS onboardingstatus;")
