"""
CRUD operations for the holiday sync module.

All functions are async and every query is scoped by organizationId
(or year/location for the master table) to prevent cross-tenant leakage.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave import Holiday, PublicHolidayMaster
from app.models.organization import Organization
from app.modules.holiday_sync.utils import HolidayRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PublicHolidayMaster helpers
# ---------------------------------------------------------------------------


async def get_master_holidays_for_year(
    year: int,
    db: AsyncSession,
    location: str = "IN-TN",
) -> list[PublicHolidayMaster]:
    """Return all master holiday rows for the given year and location."""
    result = await db.execute(
        select(PublicHolidayMaster).where(
            PublicHolidayMaster.year == year,
            PublicHolidayMaster.location == location,
        )
    )
    return list(result.scalars().all())


async def upsert_master_holidays(
    records: list[HolidayRecord],
    db: AsyncSession,
    location: str = "IN-TN",
) -> int:
    """
    Insert holiday records into PublicHolidayMaster, skipping duplicates
    (unique constraint: date + name + location).

    Returns the number of rows actually inserted.
    """
    if not records:
        return 0

    values = [
        {
            "name": r.name,
            "date": r.holiday_date,
            "year": r.year,
            "location": location,
            "isHoliday": r.is_holiday,
            "description": r.description,
        }
        for r in records
    ]

    stmt = (
        pg_insert(PublicHolidayMaster)
        .values(values)
        .on_conflict_do_nothing(
            constraint="public_holiday_master_date_name_location_key"
        )
    )
    result = await db.execute(stmt)
    await db.commit()

    inserted = result.rowcount if result.rowcount is not None else 0
    logger.info("Upserted %d rows into PublicHolidayMaster", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Organization Holiday helpers
# ---------------------------------------------------------------------------


async def get_all_organization_ids(db: AsyncSession) -> list[str]:
    """Return the IDs of every organization in the system."""
    result = await db.execute(select(Organization.id))
    return list(result.scalars().all())


async def get_existing_holiday_dates_for_org(
    organization_id: str,
    year: int,
    db: AsyncSession,
) -> set[tuple[str, dt.date]]:
    """
    Return a set of (name, date) tuples for holidays already present in the
    org's Holiday table for the given year (excluding soft-deleted rows).
    """
    result = await db.execute(
        select(Holiday.name, Holiday.holidayDate).where(
            Holiday.organizationId == organization_id,
            Holiday.holidayDate >= dt.date(year, 1, 1),
            Holiday.holidayDate <= dt.date(year, 12, 31),
            Holiday.deletedAt.is_(None),
        )
    )
    return {(row.name, row.holidayDate) for row in result.all()}


async def copy_holidays_to_org(
    organization_id: str,
    records: list[HolidayRecord],
    db: AsyncSession,
) -> int:
    """
    Insert HolidayRecord objects into the Holiday table for a specific org,
    skipping any (organizationId, holidayDate, name) tuples that already exist.

    Because the holiday table has no unique constraint in the DB we pre-filter
    existing rows rather than relying on ON CONFLICT.

    Returns the number of rows actually inserted.
    """
    if not records:
        return 0

    existing = await get_existing_holiday_dates_for_org(
        organization_id, records[0].year, db
    )

    new_records = [
        r for r in records
        if (r.name, r.holiday_date) not in existing
    ]

    if not new_records:
        logger.info("No new holidays to insert for org %s", organization_id)
        return 0

    values = [
        {
            "organizationId": organization_id,
            "name": r.name,
            "holidayDate": r.holiday_date,
            "isHoliday": r.is_holiday,
            "isRecurring": r.is_recurring,
            "description": r.description,
        }
        for r in new_records
    ]

    stmt = pg_insert(Holiday).values(values)
    result = await db.execute(stmt)
    await db.commit()

    inserted = result.rowcount if result.rowcount is not None else len(new_records)
    logger.info("Inserted %d holiday rows for org %s", inserted, organization_id)
    return inserted


async def copy_master_to_org(
    organization_id: str,
    master_rows: list[PublicHolidayMaster],
    db: AsyncSession,
) -> int:
    """
    Copy PublicHolidayMaster rows into the org's Holiday table,
    skipping rows that already exist.

    isHoliday is read directly from the master row — it was set correctly
    when the master was populated via fetch_holidays_from_api.
    """
    records: list[HolidayRecord] = [
        HolidayRecord(
            name=row.name,
            holiday_date=row.date,
            year=row.year,
            is_holiday=row.isHoliday,
            is_recurring=row.isHoliday,  # mandatory holidays are always recurring
            description=row.description,
        )
        for row in master_rows
    ]
    return await copy_holidays_to_org(organization_id, records, db)
