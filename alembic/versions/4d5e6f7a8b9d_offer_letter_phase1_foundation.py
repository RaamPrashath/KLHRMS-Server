"""offer letter phase 1 foundation

Revision ID: 4d5e6f7a8b9d
Revises: 5e6f7a8b9c0d
Create Date: 2026-05-27 22:55:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "4d5e6f7a8b9d"
down_revision: str | Sequence[str] | None = "5e6f7a8b9c0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'offertemplatestatus') THEN
                CREATE TYPE offertemplatestatus AS ENUM ('DRAFT', 'ACTIVE', 'ARCHIVED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'offerdispatchbatchstatus') THEN
                CREATE TYPE offerdispatchbatchstatus AS ENUM (
                    'QUEUED',
                    'PROCESSING',
                    'COMPLETED',
                    'PARTIAL_FAILED',
                    'FAILED'
                );
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS offer_template (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            name VARCHAR(120) NOT NULL,
            description TEXT,
            status offertemplatestatus NOT NULL DEFAULT 'DRAFT',
            "logoUrl" TEXT,
            "signatureUrl" TEXT,
            "signatoryName" VARCHAR(160),
            "signatoryTitle" VARCHAR(160),
            "footerHtml" TEXT,
            "lastUsedAt" TIMESTAMPTZ,
            "createdByMemberId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            "updatedByMemberId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_offer_template_org_name UNIQUE ("organizationId", name)
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_organizationId" ON offer_template ("organizationId")'
    )
    op.execute('CREATE INDEX IF NOT EXISTS ix_offer_template_org_status ON offer_template ("organizationId", status)')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_template_org_last_used ON offer_template ("organizationId", "lastUsedAt")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_createdByMemberId" ON offer_template ("createdByMemberId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_updatedByMemberId" ON offer_template ("updatedByMemberId")'
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_offer_template_status" ON offer_template (status)')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS offer_template_category (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "templateId" VARCHAR(36) NOT NULL REFERENCES offer_template(id) ON DELETE CASCADE,
            name VARCHAR(80) NOT NULL,
            slug VARCHAR(100) NOT NULL,
            "order" INTEGER NOT NULL DEFAULT 1,
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_offer_template_category_template_slug UNIQUE ("templateId", slug)
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_category_organizationId" ON offer_template_category ("organizationId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_category_templateId" ON offer_template_category ("templateId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_template_category_org_template ON offer_template_category ("organizationId", "templateId")'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS offer_template_section (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "templateId" VARCHAR(36) NOT NULL REFERENCES offer_template(id) ON DELETE CASCADE,
            "categoryId" VARCHAR(36) NOT NULL REFERENCES offer_template_category(id) ON DELETE CASCADE,
            "sectionKey" VARCHAR(80) NOT NULL,
            "sectionName" VARCHAR(120) NOT NULL,
            "order" INTEGER NOT NULL DEFAULT 1,
            "tiptapJson" JSONB NOT NULL DEFAULT '{}'::jsonb,
            html TEXT NOT NULL DEFAULT '',
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_offer_template_section_category_key UNIQUE ("categoryId", "sectionKey")
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_section_organizationId" ON offer_template_section ("organizationId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_section_templateId" ON offer_template_section ("templateId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_template_section_categoryId" ON offer_template_section ("categoryId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_template_section_org_template ON offer_template_section ("organizationId", "templateId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_template_section_org_category ON offer_template_section ("organizationId", "categoryId")'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS offer_dispatch_batch (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "jobPostingId" VARCHAR(36) NOT NULL REFERENCES job_posting(id) ON DELETE CASCADE,
            "stageId" VARCHAR(36) REFERENCES pipeline_stage(id) ON DELETE SET NULL,
            "templateId" VARCHAR(36) REFERENCES offer_template(id) ON DELETE SET NULL,
            "templateCategoryId" VARCHAR(36) REFERENCES offer_template_category(id) ON DELETE SET NULL,
            status offerdispatchbatchstatus NOT NULL DEFAULT 'QUEUED',
            "candidateCount" INTEGER NOT NULL DEFAULT 0,
            "successCount" INTEGER NOT NULL DEFAULT 0,
            "failureCount" INTEGER NOT NULL DEFAULT 0,
            "createdByMemberId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
            "completedAt" TIMESTAMPTZ,
            "errorSummary" TEXT
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_dispatch_batch_organizationId" ON offer_dispatch_batch ("organizationId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_dispatch_batch_jobPostingId" ON offer_dispatch_batch ("jobPostingId")'
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_offer_dispatch_batch_stageId" ON offer_dispatch_batch ("stageId")')
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_dispatch_batch_templateId" ON offer_dispatch_batch ("templateId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_dispatch_batch_templateCategoryId" ON offer_dispatch_batch ("templateCategoryId")'
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_offer_dispatch_batch_status" ON offer_dispatch_batch (status)')
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_dispatch_batch_createdByMemberId" ON offer_dispatch_batch ("createdByMemberId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_dispatch_batch_org_job ON offer_dispatch_batch ("organizationId", "jobPostingId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_dispatch_batch_org_stage ON offer_dispatch_batch ("organizationId", "stageId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_dispatch_batch_org_status ON offer_dispatch_batch ("organizationId", status)'
    )

    op.execute('DROP INDEX IF EXISTS "ix_offer_letter_applicationId"')
    op.execute('ALTER TABLE offer_letter DROP CONSTRAINT IF EXISTS "offer_letter_applicationId_key"')
    op.execute(
        """
        ALTER TABLE offer_letter
            ADD COLUMN IF NOT EXISTS "batchId" VARCHAR(36),
            ADD COLUMN IF NOT EXISTS "templateId" VARCHAR(36),
            ADD COLUMN IF NOT EXISTS "templateCategoryId" VARCHAR(36),
            ADD COLUMN IF NOT EXISTS "templateSnapshotJson" JSONB,
            ADD COLUMN IF NOT EXISTS "stageId" VARCHAR(36),
            ADD COLUMN IF NOT EXISTS "renderedHtml" TEXT,
            ADD COLUMN IF NOT EXISTS "storageBucket" VARCHAR(120),
            ADD COLUMN IF NOT EXISTS "storagePath" TEXT,
            ADD COLUMN IF NOT EXISTS "fileName" VARCHAR(255),
            ADD COLUMN IF NOT EXISTS "emailSentAt" TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS "emailError" TEXT,
            ADD COLUMN IF NOT EXISTS "responseIgnoredAt" TIMESTAMPTZ
        """
    )
    for constraint_name, column_name, table_name in (
        ("offer_letter_batchId_fkey", "batchId", "offer_dispatch_batch"),
        ("offer_letter_templateId_fkey", "templateId", "offer_template"),
        ("offer_letter_templateCategoryId_fkey", "templateCategoryId", "offer_template_category"),
        ("offer_letter_stageId_fkey", "stageId", "pipeline_stage"),
    ):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{constraint_name}'
                ) THEN
                    ALTER TABLE offer_letter
                        ADD CONSTRAINT "{constraint_name}"
                        FOREIGN KEY ("{column_name}")
                        REFERENCES {table_name}(id)
                        ON DELETE SET NULL;
                END IF;
            END $$;
            """
        )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_offer_letter_applicationId" ON offer_letter ("applicationId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_offer_letter_batchId" ON offer_letter ("batchId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_offer_letter_templateId" ON offer_letter ("templateId")')
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_offer_letter_templateCategoryId" ON offer_letter ("templateCategoryId")'
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_offer_letter_stageId" ON offer_letter ("stageId")')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_letter_org_application ON offer_letter ("organizationId", "applicationId")'
    )
    op.execute('CREATE INDEX IF NOT EXISTS ix_offer_letter_org_batch ON offer_letter ("organizationId", "batchId")')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_offer_letter_org_template ON offer_letter ("organizationId", "templateId")'
    )
    op.execute('CREATE INDEX IF NOT EXISTS ix_offer_letter_org_stage ON offer_letter ("organizationId", "stageId")')
    op.execute('CREATE INDEX IF NOT EXISTS ix_offer_letter_org_status ON offer_letter ("organizationId", status)')


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_offer_letter_org_status')
    op.execute('DROP INDEX IF EXISTS ix_offer_letter_org_stage')
    op.execute('DROP INDEX IF EXISTS ix_offer_letter_org_template')
    op.execute('DROP INDEX IF EXISTS ix_offer_letter_org_batch')
    op.execute('DROP INDEX IF EXISTS ix_offer_letter_org_application')
    op.execute('DROP INDEX IF EXISTS "ix_offer_letter_stageId"')
    op.execute('DROP INDEX IF EXISTS "ix_offer_letter_templateCategoryId"')
    op.execute('DROP INDEX IF EXISTS "ix_offer_letter_templateId"')
    op.execute('DROP INDEX IF EXISTS "ix_offer_letter_batchId"')
    op.execute('DROP INDEX IF EXISTS "ix_offer_letter_applicationId"')
    op.execute('ALTER TABLE offer_letter DROP CONSTRAINT IF EXISTS "offer_letter_stageId_fkey"')
    op.execute('ALTER TABLE offer_letter DROP CONSTRAINT IF EXISTS "offer_letter_templateCategoryId_fkey"')
    op.execute('ALTER TABLE offer_letter DROP CONSTRAINT IF EXISTS "offer_letter_templateId_fkey"')
    op.execute('ALTER TABLE offer_letter DROP CONSTRAINT IF EXISTS "offer_letter_batchId_fkey"')
    op.execute(
        """
        ALTER TABLE offer_letter
            DROP COLUMN IF EXISTS "responseIgnoredAt",
            DROP COLUMN IF EXISTS "emailError",
            DROP COLUMN IF EXISTS "emailSentAt",
            DROP COLUMN IF EXISTS "fileName",
            DROP COLUMN IF EXISTS "storagePath",
            DROP COLUMN IF EXISTS "storageBucket",
            DROP COLUMN IF EXISTS "renderedHtml",
            DROP COLUMN IF EXISTS "stageId",
            DROP COLUMN IF EXISTS "templateSnapshotJson",
            DROP COLUMN IF EXISTS "templateCategoryId",
            DROP COLUMN IF EXISTS "templateId",
            DROP COLUMN IF EXISTS "batchId"
        """
    )
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS "ix_offer_letter_applicationId" ON offer_letter ("applicationId")')
    op.execute("DROP TABLE IF EXISTS offer_dispatch_batch")
    op.execute("DROP TABLE IF EXISTS offer_template_section")
    op.execute("DROP TABLE IF EXISTS offer_template_category")
    op.execute("DROP TABLE IF EXISTS offer_template")
    op.execute("DROP TYPE IF EXISTS offerdispatchbatchstatus")
    op.execute("DROP TYPE IF EXISTS offertemplatestatus")
