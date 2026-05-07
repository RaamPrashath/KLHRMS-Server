"""
Holiday sync service layer.

Two entry points:
  - `run_annual_sync(year, db)` — called by the Jan 1st cron job.
  - `run_org_sync(organization_id, year, db)` — called by the manual sync endpoint.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.holiday_sync.crud import (
    copy_holidays_to_org,
    copy_master_to_org,
    get_all_organization_ids,
    get_master_holidays_for_year,
    upsert_master_holidays,
)
from app.modules.holiday_sync.utils import fetch_holidays_from_api

logger = logging.getLogger(__name__)


async def run_annual_sync(year: int, db: AsyncSession) -> dict[str, int]:
    """
    Full annual sync — intended for the Jan 1st cron job.

    Steps:
      1. Fetch holiday data from the external API for `year`.
      2. Upsert all records into PublicHolidayMaster.
      3. For every organization, copy the records into their Holiday table.

    Returns a summary dict with counts.
    """
    logger.info("Starting annual holiday sync for year %d", year)

    # 1. Fetch from external API
    records = await fetch_holidays_from_api(year)

    # 2. Persist to master table
    master_inserted = await upsert_master_holidays(records, db)

    # 3. Propagate to all organizations
    org_ids = await get_all_organization_ids(db)
    total_org_rows = 0
    for org_id in org_ids:
        inserted = await copy_holidays_to_org(org_id, records, db)
        total_org_rows += inserted

    summary = {
        "year": year,
        "master_inserted": master_inserted,
        "organizations_processed": len(org_ids),
        "org_rows_inserted": total_org_rows,
    }
    logger.info("Annual sync complete: %s", summary)
    return summary


async def run_org_sync(organization_id: str, year: int, db: AsyncSession) -> dict[str, int]:
    """
    Per-organization manual sync — called by the POST /holidays/sync endpoint.

    Steps:
      1. Check if PublicHolidayMaster already has data for `year`.
      2a. If NO  → fetch from API, populate master, then copy to org.
      2b. If YES → copy missing records from master directly to org.

    Returns a summary dict with counts.
    """
    logger.info("Starting org sync for org=%s year=%d", organization_id, year)

    master_rows = await get_master_holidays_for_year(year, db)

    if not master_rows:
        # Master table is empty for this year — fetch from API first
        logger.info("Master table empty for year %d — fetching from API", year)
        records = await fetch_holidays_from_api(year)
        await upsert_master_holidays(records, db)
        inserted = await copy_holidays_to_org(organization_id, records, db)
        source = "api"
    else:
        # Master table already populated — copy only missing rows to org
        logger.info(
            "Master table has %d rows for year %d — copying to org %s",
            len(master_rows),
            year,
            organization_id,
        )
        inserted = await copy_master_to_org(organization_id, master_rows, db)
        source = "master"

    summary = {
        "year": year,
        "organization_id": organization_id,
        "rows_inserted": inserted,
        "source": source,  # type: ignore[dict-item]
    }
    logger.info("Org sync complete: %s", summary)
    return summary
