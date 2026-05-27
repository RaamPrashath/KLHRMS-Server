"""remove manual evaluation marks

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-05-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "4d5e6f7a8b9c"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS interview_feedback_value CASCADE")
    op.execute("DROP TABLE IF EXISTS stage_evaluation_workspace CASCADE")
    op.execute("DROP TABLE IF EXISTS stage_evaluation_category CASCADE")

    op.execute('ALTER TABLE pipeline_stage DROP COLUMN IF EXISTS "evaluationEnabled"')
    op.execute('ALTER TABLE pipeline_stage DROP COLUMN IF EXISTS "sheetEnabled"')
    op.execute('ALTER TABLE pipeline_stage DROP COLUMN IF EXISTS "evaluationType"')
    op.execute('ALTER TABLE pipeline_stage DROP COLUMN IF EXISTS "evaluationIncludeTotal"')
    op.execute('ALTER TABLE pipeline_stage DROP COLUMN IF EXISTS "evaluationIncludeAnalysis"')

    op.execute("ALTER TABLE candidate_application DROP COLUMN IF EXISTS score")
    op.execute("ALTER TABLE candidate_application DROP COLUMN IF EXISTS rating")
    op.execute("ALTER TABLE interview_feedback DROP COLUMN IF EXISTS score")


def downgrade() -> None:
    op.execute("ALTER TABLE interview_feedback ADD COLUMN IF NOT EXISTS score INTEGER")
    op.execute("ALTER TABLE candidate_application ADD COLUMN IF NOT EXISTS rating INTEGER")
    op.execute("ALTER TABLE candidate_application ADD COLUMN IF NOT EXISTS score INTEGER")

    op.execute(
        'ALTER TABLE pipeline_stage ADD COLUMN IF NOT EXISTS "evaluationIncludeAnalysis" BOOLEAN NOT NULL DEFAULT false'
    )
    op.execute(
        'ALTER TABLE pipeline_stage ADD COLUMN IF NOT EXISTS "evaluationIncludeTotal" BOOLEAN NOT NULL DEFAULT false'
    )
    op.execute('ALTER TABLE pipeline_stage ADD COLUMN IF NOT EXISTS "evaluationType" VARCHAR(32)')
    op.execute(
        'ALTER TABLE pipeline_stage ADD COLUMN IF NOT EXISTS "sheetEnabled" BOOLEAN NOT NULL DEFAULT false'
    )
    op.execute(
        'ALTER TABLE pipeline_stage ADD COLUMN IF NOT EXISTS "evaluationEnabled" BOOLEAN NOT NULL DEFAULT false'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stage_evaluation_category (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "stageId" VARCHAR(36) NOT NULL REFERENCES pipeline_stage(id) ON DELETE CASCADE,
            name VARCHAR(120) NOT NULL,
            "valueType" VARCHAR(32) NOT NULL DEFAULT 'NUMERIC',
            "maxScore" INTEGER,
            "order" INTEGER NOT NULL,
            "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT now(),
            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT now(),
            CONSTRAINT uq_stage_evaluation_category_order UNIQUE ("stageId", "order")
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_stage_evaluation_category_organizationId" ON stage_evaluation_category ("organizationId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_stage_evaluation_category_stageId" ON stage_evaluation_category ("stageId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_stage_evaluation_category_org_stage ON stage_evaluation_category ("organizationId", "stageId")'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stage_evaluation_workspace (
            id VARCHAR(36) PRIMARY KEY,
            "organizationId" VARCHAR(36) NOT NULL REFERENCES organization(id) ON DELETE CASCADE,
            "stageId" VARCHAR(36) NOT NULL REFERENCES pipeline_stage(id) ON DELETE CASCADE,
            "googleSpreadsheetId" VARCHAR(255) NOT NULL,
            "googleSpreadsheetUrl" TEXT NOT NULL,
            "googleSheetId" INTEGER,
            "googleSheetTitle" VARCHAR(100) NOT NULL,
            "createdByMemberId" VARCHAR(36) REFERENCES member(id) ON DELETE SET NULL,
            "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT now(),
            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT now(),
            CONSTRAINT uq_stage_evaluation_workspace_stage UNIQUE ("stageId"),
            CONSTRAINT uq_stage_evaluation_workspace_org_stage UNIQUE ("organizationId", "stageId")
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_stage_evaluation_workspace_createdByMemberId" ON stage_evaluation_workspace ("createdByMemberId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_stage_evaluation_workspace_organizationId" ON stage_evaluation_workspace ("organizationId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_stage_evaluation_workspace_stageId" ON stage_evaluation_workspace ("stageId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_stage_evaluation_workspace_org_stage ON stage_evaluation_workspace ("organizationId", "stageId")'
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interview_feedback_value (
            id VARCHAR(36) PRIMARY KEY,
            "feedbackId" VARCHAR(36) NOT NULL REFERENCES interview_feedback(id) ON DELETE CASCADE,
            "categoryId" VARCHAR(36) NOT NULL REFERENCES stage_evaluation_category(id) ON DELETE CASCADE,
            "numericValue" DOUBLE PRECISION,
            "textValue" TEXT,
            "booleanValue" BOOLEAN,
            "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT now(),
            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT now(),
            CONSTRAINT uq_interview_feedback_value_category UNIQUE ("feedbackId", "categoryId")
        )
        """
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_interview_feedback_value_feedbackId" ON interview_feedback_value ("feedbackId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "ix_interview_feedback_value_categoryId" ON interview_feedback_value ("categoryId")'
    )
