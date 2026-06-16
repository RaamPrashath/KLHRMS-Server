"""document collection templates

Revision ID: 8f4b2d1c9a7e
Revises: 1cff6f7e415e
Create Date: 2026-06-15 16:20:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "8f4b2d1c9a7e"
down_revision = "1cff6f7e415e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documentcollectiontemplatestatus') THEN
                CREATE TYPE documentcollectiontemplatestatus AS ENUM ('DRAFT', 'ACTIVE', 'ARCHIVED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documentcollectionfieldtype') THEN
                CREATE TYPE documentcollectionfieldtype AS ENUM ('FILE_UPLOAD', 'SHORT_TEXT', 'LONG_TEXT', 'DATE');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documentcollectionallowedformatgroup') THEN
                CREATE TYPE documentcollectionallowedformatgroup AS ENUM ('IMAGE', 'FILE', 'VIDEO', 'ALL');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'documentcollectionrequeststatus') THEN
                CREATE TYPE documentcollectionrequeststatus AS ENUM ('PENDING', 'SUBMITTED', 'FAILED');
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_collection_template (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            name VARCHAR(120) NOT NULL,
            description TEXT,
            status documentcollectiontemplatestatus NOT NULL DEFAULT 'DRAFT',
            "lastUsedAt" TIMESTAMP WITH TIME ZONE,
            "createdByMemberId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            "updatedByMemberId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            CONSTRAINT uq_document_collection_template_org_name UNIQUE ("organizationId", name)
        );
        """
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_template_organizationId" ON document_collection_template ("organizationId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_template_createdByMemberId" ON document_collection_template ("createdByMemberId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_template_updatedByMemberId" ON document_collection_template ("updatedByMemberId")')
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_collection_template_org_status ON document_collection_template ("organizationId", status)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_collection_template_org_last_used ON document_collection_template ("organizationId", "lastUsedAt")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_template_status" ON document_collection_template (status)')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_collection_field (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "templateId" VARCHAR(36) NOT NULL REFERENCES document_collection_template(id) ON DELETE CASCADE,
            "fieldType" documentcollectionfieldtype NOT NULL DEFAULT 'FILE_UPLOAD',
            name VARCHAR(120) NOT NULL,
            description TEXT,
            required BOOLEAN NOT NULL DEFAULT TRUE,
            "order" INTEGER NOT NULL DEFAULT 1,
            "allowedFormatGroup" documentcollectionallowedformatgroup NOT NULL DEFAULT 'ALL',
            "maxSizeBytes" BIGINT,
            "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
        """
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_field_organizationId" ON document_collection_field ("organizationId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_field_templateId" ON document_collection_field ("templateId")')
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_collection_field_org_template ON document_collection_field ("organizationId", "templateId")')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_collection_request (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "applicationId" VARCHAR(36) NOT NULL REFERENCES candidate_application(id) ON DELETE CASCADE,
            "templateId" VARCHAR(36) REFERENCES document_collection_template(id) ON DELETE SET NULL,
            "candidateToken" VARCHAR NOT NULL UNIQUE,
            status documentcollectionrequeststatus NOT NULL DEFAULT 'PENDING',
            "templateSnapshotJson" JSONB NOT NULL DEFAULT '{}'::jsonb,
            "answersJson" JSONB,
            "tokenSentAt" TIMESTAMP WITH TIME ZONE,
            "emailSentAt" TIMESTAMP WITH TIME ZONE,
            "submittedAt" TIMESTAMP WITH TIME ZONE,
            "emailError" TEXT,
            "createdByMemberId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
        """
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_request_organizationId" ON document_collection_request ("organizationId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_request_applicationId" ON document_collection_request ("applicationId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_request_templateId" ON document_collection_request ("templateId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_request_createdByMemberId" ON document_collection_request ("createdByMemberId")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_document_collection_request_status" ON document_collection_request (status)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_collection_request_org_application ON document_collection_request ("organizationId", "applicationId")')
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_collection_request_org_template ON document_collection_request ("organizationId", "templateId")')
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_collection_request_org_status ON document_collection_request ("organizationId", status)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_document_collection_request_token ON document_collection_request ("candidateToken")')
    op.execute(
        """
        UPDATE role
        SET
            permissions = jsonb_set(
                COALESCE(permissions, '{}'::jsonb),
                '{documentCollection}',
                CASE
                    WHEN name IN ('Admin', 'HR Manager') THEN
                        '{"view":"organization","create":"organization","edit":"organization","delete":"organization","approve":"none"}'::jsonb
                    WHEN name = 'Employee' THEN
                        '{"view":"self","create":"self","edit":"none","delete":"none","approve":"none"}'::jsonb
                    ELSE
                        '{"view":"none","create":"none","edit":"none","delete":"none","approve":"none"}'::jsonb
                END,
                true
            ),
            "updatedAt" = now()
        WHERE NOT (COALESCE(permissions, '{}'::jsonb) ? 'documentCollection');
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS document_collection_request")
    op.execute("DROP TABLE IF EXISTS document_collection_field")
    op.execute("DROP TABLE IF EXISTS document_collection_template")
    op.execute("DROP TYPE IF EXISTS documentcollectionrequeststatus")
    op.execute("DROP TYPE IF EXISTS documentcollectionallowedformatgroup")
    op.execute("DROP TYPE IF EXISTS documentcollectionfieldtype")
    op.execute("DROP TYPE IF EXISTS documentcollectiontemplatestatus")
