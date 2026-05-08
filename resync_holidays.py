"""
One-shot script: clear stale holiday data for the current year and re-sync
from the Calendarific API so isHoliday / isRecurring flags are correct.

Run with:  uv run python resync_holidays.py
"""

import asyncio
import datetime as dt

from dotenv import load_dotenv

load_dotenv()

from app.shared.database import AsyncSessionLocal  # noqa: E402
from app.models.leave import Holiday, PublicHolidayMaster  # noqa: E402
from app.modules.holiday_sync.service import run_annual_sync  # noqa: E402
from sqlalchemy import delete  # noqa: E402


async def main() -> None:
    year = dt.date.today().year
    print(f"Re-syncing holidays for year {year} ...")

    async with AsyncSessionLocal() as db:
        # 1. Delete existing org holiday rows for this year
        deleted_org = await db.execute(
            delete(Holiday).where(
                Holiday.holidayDate >= dt.date(year, 1, 1),
                Holiday.holidayDate <= dt.date(year, 12, 31),
            )
        )
        print(f"  Deleted {deleted_org.rowcount} rows from holiday table")

        # 2. Delete existing master rows for this year
        deleted_master = await db.execute(
            delete(PublicHolidayMaster).where(
                PublicHolidayMaster.year == year,
            )
        )
        print(f"  Deleted {deleted_master.rowcount} rows from public_holiday_master table")

        await db.commit()

        # 3. Re-fetch from API and populate everything
        summary = await run_annual_sync(year=year, db=db)
        print(f"  Sync complete: {summary}")


if __name__ == "__main__":
    asyncio.run(main())
