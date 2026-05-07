"""
Holiday transformation utilities.

Responsibilities:
- Fetch raw holiday data from the Calendarific API.
- Determine whether a holiday is mandatory (isHoliday = True, isRecurring = True)
  using fuzzy normalized name matching — lowercase, strip spaces/punctuation,
  then check substring in both directions.
- Expand Diwali / Pongal into a 4-day cluster.
- Return a flat list of `HolidayRecord` dataclasses ready for DB insertion.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field

import httpx

from app.shared.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CALENDARIFIC_API_URL = "https://calendarific.com/api/v2/holidays"
COUNTRY = "IN"
STATE = "IN-TN"


# ---------------------------------------------------------------------------
# Normalization helper (defined early — used by the constants below)
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase, remove all spaces and non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# ---------------------------------------------------------------------------
# Mandatory holiday keywords
#
# These are the canonical names as the user defined them.  They are normalized
# (lowercase, no spaces/punctuation) before comparison, so "Christmas Day" and
# "Christmas" both match, "Deepavali" matches "Diwali/Deepavali", etc.
#
# Matching rule: normalize(api_name) contains normalize(keyword)
#                OR normalize(keyword) contains normalize(api_name)
# ---------------------------------------------------------------------------

MANDATORY_KEYWORDS: tuple[str, ...] = (
    "new year's day",
    "pongal",
    "thiruvalluvar day",
    "uzhavar thirunal",
    "republic day",
    "telugu new year",          # covers "Ugadi" via alias check below
    "ugadi",                    # Telugu New Year's Day
    "ramzan",                   # Ramzan Id / Eid-ul-Fitr
    "id-ul-fitr",
    "eid ul fitar",
    "mahaveer jayanthi",
    "mahavir jayanti",
    "good friday",
    "tamil new year",
    "mesadi",                   # Tamil New Year's Day (alternate API name)
    "vaisakhi",                 # Tamil New Year's Day (alternate API name)
    "ambedkar",                 # Dr. B.R. Ambedkar's Birthday / Ambedkar Jayanti
    "may day",
    "international worker",     # International Worker's Day
    "bakrid",
    "id-ul-adha",
    "eid ul adha",
    "muharram",
    "independence day",
    "krishna jayanthi",
    "janmashtami",              # Krishna Jayanthi
    "milad",                    # Milad-un-Nabi / Milad un-Nabi
    "vinayakar",                # Vinayakar Chathurthi
    "ganesh chaturthi",
    "gandhi jayanti",
    "mahatma gandhi",
    "ayutha pooja",
    "maha ashtami",             # Ayutha Pooja falls on Maha Ashtami
    "vijaya dasami",
    "dussehra",                 # Vijaya Dasami
    "deepavali",
    "diwali",
    "christmas",
)

# Normalized keyword set (computed once at import time)
_NORM_KEYWORDS: tuple[str, ...] = tuple(
    _normalize(k) for k in MANDATORY_KEYWORDS
)

# urlids whose holiday should be expanded into a 4-day cluster.
CLUSTER_URLIDS: frozenset[str] = frozenset(
    {
        "india/pongal",
        "india/diwali",
    }
)


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------


@dataclass
class HolidayRecord:
    """Flat representation of a single holiday row to be inserted."""

    name: str
    holiday_date: dt.date
    year: int
    is_holiday: bool
    is_recurring: bool
    description: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_mandatory(name: str) -> bool:
    """
    Return True if the holiday name fuzzy-matches any mandatory keyword.

    Both the API name and each keyword are normalized before comparison.
    A match occurs when either string contains the other as a substring.
    """
    norm_name = _normalize(name)
    return any(
        kw in norm_name or norm_name in kw
        for kw in _NORM_KEYWORDS
    )


def _extract_urlid(item: dict) -> str:
    return (item.get("urlid") or "").strip().lower()


def _build_cluster(name: str, base_date: dt.date, description: str | None) -> list[HolidayRecord]:
    """
    Expand a cluster holiday into 4 consecutive days:
      base_date - 1  (Eve)
      base_date      (exact day)
      base_date + 1  (Day 2)
      base_date + 2  (Day 3)

    All 4 days are marked isHoliday = True, isRecurring = True.
    """
    offsets_and_labels = [
        (-1, f"{name} Eve"),
        (0, name),
        (1, f"{name} (Day 2)"),
        (2, f"{name} (Day 3)"),
    ]
    return [
        HolidayRecord(
            name=label,
            holiday_date=base_date + dt.timedelta(days=offset),
            year=base_date.year,
            is_holiday=True,
            is_recurring=True,
            description=description,
        )
        for offset, label in offsets_and_labels
    ]


def _parse_raw_holidays(raw_holidays: list[dict]) -> list[HolidayRecord]:
    """
    Convert the raw Calendarific response list into a flat list of
    HolidayRecord objects, applying cluster expansion and mandatory flags.
    """
    records: list[HolidayRecord] = []

    for item in raw_holidays:
        name: str = item.get("name", "").strip()
        description: str | None = item.get("description") or None
        urlid = _extract_urlid(item)

        date_obj = item.get("date", {})
        iso_str: str | None = date_obj.get("iso")
        if not iso_str:
            logger.warning("Skipping holiday with missing date: %s", name)
            continue

        try:
            holiday_date = dt.date.fromisoformat(iso_str[:10])
        except ValueError:
            logger.warning("Skipping holiday with unparseable date '%s': %s", iso_str, name)
            continue

        if urlid in CLUSTER_URLIDS:
            records.extend(_build_cluster(name, holiday_date, description))
        else:
            mandatory = _is_mandatory(name)
            records.append(
                HolidayRecord(
                    name=name,
                    holiday_date=holiday_date,
                    year=holiday_date.year,
                    is_holiday=mandatory,
                    is_recurring=mandatory,
                    description=description,
                )
            )

    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_holidays_from_api(year: int) -> list[HolidayRecord]:
    """
    Fetch public holidays for the given year from the Calendarific API and
    return a list of HolidayRecord objects with mandatory/cluster logic applied.
    """
    settings = get_settings()
    api_key = settings.calendarific_api_key

    params = {
        "api_key": api_key,
        "country": COUNTRY,
        "year": str(year),
        "location": STATE,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(CALENDARIFIC_API_URL, params=params)
        response.raise_for_status()

    payload = response.json()
    raw_holidays: list[dict] = payload.get("response", {}).get("holidays", [])

    if not isinstance(raw_holidays, list):
        raise ValueError(f"Unexpected Calendarific response shape: {payload}")

    records = _parse_raw_holidays(raw_holidays)
    mandatory_count = sum(1 for r in records if r.is_holiday)
    logger.info(
        "Fetched %d holiday records (%d mandatory) for year %d",
        len(records),
        mandatory_count,
        year,
    )
    return records
