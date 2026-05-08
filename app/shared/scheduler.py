"""
APScheduler setup for KL HRMS.

The scheduler is created once at module import time and started/stopped
via FastAPI lifespan events in main.py.

Scheduled jobs
--------------
annual_holiday_sync  — runs on January 1st at 00:00 every year.
"""

from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Module-level scheduler instance — imported by main.py lifespan
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


# ---------------------------------------------------------------------------
# Job functions
# ---------------------------------------------------------------------------


async def _annual_holiday_sync_job() -> None:
    """
    Cron job: fetch public holidays for the new year and propagate them to
    every organization's Holiday table.

    Runs on January 1st at 00:00 IST.
    """
    from app.modules.holiday_sync.service import run_annual_sync
    from app.shared.database import AsyncSessionLocal

    year = dt.date.today().year
    logger.info("Annual holiday sync job triggered for year %d", year)

    async with AsyncSessionLocal() as db:
        try:
            summary = await run_annual_sync(year=year, db=db)
            logger.info("Annual holiday sync completed: %s", summary)
        except Exception:
            logger.exception("Annual holiday sync job failed for year %d", year)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_jobs() -> None:
    """
    Register all scheduled jobs on the module-level scheduler.
    Called once during application startup.
    """
    scheduler.add_job(
        _annual_holiday_sync_job,
        trigger=CronTrigger(
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            timezone="Asia/Kolkata",
        ),
        id="annual_holiday_sync",
        name="Annual Public Holiday Sync (Jan 1st)",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1 hour late if server was down
    )
    logger.info("Registered job: annual_holiday_sync (Jan 1 00:00 IST)")
