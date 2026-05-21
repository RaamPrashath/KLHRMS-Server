"""add asset maintenance ticket id

Revision ID: c1d2e3f4a5b6
Revises: f6a7b8c9d012
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "f6a7b8c9d012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute('ALTER TABLE asset_maintenance_log ADD COLUMN IF NOT EXISTS "ticketId" VARCHAR(7)')
    op.execute(
        """
        DO $$
        DECLARE
            maintenance_count INTEGER;
            ticket_offset INTEGER;
        BEGIN
            SELECT COUNT(*) INTO maintenance_count
            FROM asset_maintenance_log
            WHERE "ticketId" IS NULL;

            IF maintenance_count > 999999 THEN
                RAISE EXCEPTION 'Cannot backfill more than 999999 maintenance ticket IDs';
            END IF;

            SELECT COALESCE(MAX(substring("ticketId" FROM 2)::INTEGER), 0) INTO ticket_offset
            FROM asset_maintenance_log
            WHERE "ticketId" ~ '^#[0-9]{6}$';

            IF ticket_offset + maintenance_count > 999999 THEN
                RAISE EXCEPTION 'Cannot backfill maintenance ticket IDs without exceeding #999999';
            END IF;

            WITH numbered AS (
                SELECT
                    id,
                    row_number() OVER (ORDER BY "createdAt", id) AS rn
                FROM asset_maintenance_log
                WHERE "ticketId" IS NULL
            )
            UPDATE asset_maintenance_log AS log
            SET "ticketId" = '#' || lpad((ticket_offset + numbered.rn)::text, 6, '0')
            FROM numbered
            WHERE log.id = numbered.id;
        END $$;
        """
    )
    op.execute('ALTER TABLE asset_maintenance_log ALTER COLUMN "ticketId" SET NOT NULL')
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS "asset_maintenance_log_ticketId_key"
        ON asset_maintenance_log ("ticketId")
        """
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "asset_maintenance_log_ticketId_key"')
    op.execute('ALTER TABLE asset_maintenance_log DROP COLUMN IF EXISTS "ticketId"')
