"""repair asset maintenance ticket id drift

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute('ALTER TABLE asset_maintenance_log ADD COLUMN IF NOT EXISTS "ticketId" VARCHAR(7)')
    op.execute(
        """
        DO $$
        DECLARE
            missing_record RECORD;
            candidate_ticket_id VARCHAR(7);
            ticket_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO ticket_count
            FROM asset_maintenance_log;

            IF ticket_count > 999999 THEN
                RAISE EXCEPTION 'Cannot assign six-digit maintenance ticket IDs to more than 999999 rows';
            END IF;

            FOR missing_record IN
                SELECT id
                FROM asset_maintenance_log
                WHERE "ticketId" IS NULL
                ORDER BY "createdAt", id
            LOOP
                LOOP
                    candidate_ticket_id := '#' || lpad(floor(random() * 1000000)::int::text, 6, '0');

                    EXIT WHEN NOT EXISTS (
                        SELECT 1
                        FROM asset_maintenance_log
                        WHERE "ticketId" = candidate_ticket_id
                    );
                END LOOP;

                UPDATE asset_maintenance_log
                SET "ticketId" = candidate_ticket_id
                WHERE id = missing_record.id;
            END LOOP;
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
    op.execute('ALTER TABLE asset_maintenance_log ALTER COLUMN "ticketId" DROP NOT NULL')
