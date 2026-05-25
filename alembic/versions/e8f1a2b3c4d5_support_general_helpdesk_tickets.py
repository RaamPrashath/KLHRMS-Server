"""support general helpdesk tickets

Revision ID: e8f1a2b3c4d5
Revises: d4e5f6a7b8c9
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "e8f1a2b3c4d5"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE asset_maintenance_log ADD COLUMN IF NOT EXISTS "organizationId" VARCHAR(36)'
    )
    op.execute(
        """
        UPDATE asset_maintenance_log AS log
        SET "organizationId" = asset."organizationId"
        FROM asset
        WHERE log."assetId" = asset.id
            AND log."organizationId" IS NULL
        """
    )
    op.execute('ALTER TABLE asset_maintenance_log ALTER COLUMN "organizationId" SET NOT NULL')
    op.execute(
        "ALTER TABLE asset_maintenance_log ADD COLUMN IF NOT EXISTS \"ticketMode\" VARCHAR(40) NOT NULL DEFAULT 'ASSET_ISSUE'"
    )
    op.execute("ALTER TABLE asset_maintenance_log ADD COLUMN IF NOT EXISTS category VARCHAR(80)")
    op.execute("ALTER TABLE asset_maintenance_log ADD COLUMN IF NOT EXISTS subject VARCHAR(160)")
    op.execute(
        'ALTER TABLE asset_maintenance_log ADD COLUMN IF NOT EXISTS "attachmentsMetadata" JSONB'
    )

    op.execute('ALTER TABLE asset_maintenance_log ALTER COLUMN "assetId" DROP NOT NULL')
    op.execute(
        'ALTER TABLE asset_maintenance_log DROP CONSTRAINT IF EXISTS "asset_maintenance_log_assetId_fkey"'
    )
    op.execute(
        """
        ALTER TABLE asset_maintenance_log
        ADD CONSTRAINT "asset_maintenance_log_assetId_fkey"
        FOREIGN KEY ("assetId") REFERENCES asset (id) ON DELETE SET NULL
        """
    )

    op.execute(
        'CREATE INDEX IF NOT EXISTS "asset_maintenance_log_organizationId_idx" ON asset_maintenance_log ("organizationId")'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS "asset_maintenance_log_ticketMode_idx" ON asset_maintenance_log ("ticketMode")'
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS asset_maintenance_log_category_idx ON asset_maintenance_log (category)"
    )


def downgrade() -> None:
    op.execute('DELETE FROM asset_maintenance_log WHERE "assetId" IS NULL')
    op.execute(
        'ALTER TABLE asset_maintenance_log DROP CONSTRAINT IF EXISTS "asset_maintenance_log_assetId_fkey"'
    )
    op.execute(
        """
        ALTER TABLE asset_maintenance_log
        ADD CONSTRAINT "asset_maintenance_log_assetId_fkey"
        FOREIGN KEY ("assetId") REFERENCES asset (id) ON DELETE CASCADE
        """
    )
    op.execute('ALTER TABLE asset_maintenance_log ALTER COLUMN "assetId" SET NOT NULL')

    op.execute("DROP INDEX IF EXISTS asset_maintenance_log_category_idx")
    op.execute('DROP INDEX IF EXISTS "asset_maintenance_log_ticketMode_idx"')
    op.execute('DROP INDEX IF EXISTS "asset_maintenance_log_organizationId_idx"')
    op.execute('ALTER TABLE asset_maintenance_log DROP COLUMN IF EXISTS "attachmentsMetadata"')
    op.execute("ALTER TABLE asset_maintenance_log DROP COLUMN IF EXISTS subject")
    op.execute("ALTER TABLE asset_maintenance_log DROP COLUMN IF EXISTS category")
    op.execute('ALTER TABLE asset_maintenance_log DROP COLUMN IF EXISTS "ticketMode"')
    op.execute('ALTER TABLE asset_maintenance_log DROP COLUMN IF EXISTS "organizationId"')
