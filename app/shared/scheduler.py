"""
APScheduler setup for KL HRMS.

The scheduler is created once at module import time and started/stopped
via FastAPI lifespan events in main.py.

Scheduled jobs
--------------
annual_holiday_sync            - runs on January 1st at 00:00 every year.
warranty_tracker_scan          - runs daily at 09:00 IST.
temp_replacement_reminder_scan - runs daily at 08:00 IST.
interview_slot_reminder_scan   - runs every hour for interview slot picking reminders.
"""

from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def _annual_holiday_sync_job() -> None:
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


async def _warranty_tracker_scan_job() -> None:
    from app.modules.assets.service import run_warranty_tracker_scan
    from app.shared.database import AsyncSessionLocal

    logger.info("Warranty tracker scan job triggered")

    async with AsyncSessionLocal() as db:
        try:
            summary = await run_warranty_tracker_scan(db)
            logger.info("Warranty tracker scan completed: %s", summary)
        except Exception:
            logger.exception("Warranty tracker scan job failed")


async def _temp_replacement_reminder_job() -> None:
    from app.modules.assets.service import run_temp_replacement_reminder_scan
    from app.shared.database import AsyncSessionLocal

    logger.info("Temp replacement reminder scan job triggered")

    async with AsyncSessionLocal() as db:
        try:
            summary = await run_temp_replacement_reminder_scan(db)
            logger.info("Temp replacement reminder scan completed: %s", summary)
        except Exception:
            logger.exception("Temp replacement reminder scan job failed")


async def _interview_slot_reminder_job() -> None:
    from app.modules.candidates.service import process_interview_slot_reminders
    from app.shared.database import AsyncSessionLocal

    logger.info("Interview slot reminder scan job triggered")

    async with AsyncSessionLocal() as db:
        try:
            summary = await process_interview_slot_reminders(db)
            logger.info("Interview slot reminder scan completed: %s", summary)
        except Exception:
            logger.exception("Interview slot reminder scan job failed")


def register_jobs() -> None:
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
        misfire_grace_time=3600,
    )
    logger.info("Registered job: annual_holiday_sync (Jan 1 00:00 IST)")

    scheduler.add_job(
        _warranty_tracker_scan_job,
        trigger=CronTrigger(
            hour=9,
            minute=0,
            second=0,
            timezone="Asia/Kolkata",
        ),
        id="warranty_tracker_scan",
        name="Warranty Tracker Scan (Daily 09:00 IST)",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered job: warranty_tracker_scan (Daily 09:00 IST)")

    scheduler.add_job(
        _temp_replacement_reminder_job,
        trigger=CronTrigger(
            hour=8,
            minute=0,
            second=0,
            timezone="Asia/Kolkata",
        ),
        id="temp_replacement_reminder_scan",
        name="Temp Replacement Reminder Scan (Daily 08:00 IST)",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered job: temp_replacement_reminder_scan (Daily 08:00 IST)")

    scheduler.add_job(
        _interview_slot_reminder_job,
        trigger=CronTrigger(
            minute="0",
            timezone="Asia/Kolkata",
        ),
        id="interview_slot_reminder_scan",
        name="Interview Slot Reminder Scan (Every hour)",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered job: interview_slot_reminder_scan (Every hour)")
