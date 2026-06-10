"""Shared weekly plan location definitions."""

from __future__ import annotations

from enum import Enum


class PlanLocationValue(str, Enum):
    OFFICE = "OFFICE"
    WFH = "WFH"
    LEAVE = "LEAVE"
    HOLIDAY = "HOLIDAY"


PLAN_LOCATION_OPTIONS = (
    {
        "value": PlanLocationValue.OFFICE,
        "label": "Office",
        "short_label": "OFF",
        "color": "#0f766e",
    },
    {
        "value": PlanLocationValue.WFH,
        "label": "WFH",
        "short_label": "WFH",
        "color": "#2563eb",
    },
    {
        "value": PlanLocationValue.LEAVE,
        "label": "Leave",
        "short_label": "LV",
        "color": "#dc2626",
    },
    {
        "value": PlanLocationValue.HOLIDAY,
        "label": "Holiday",
        "short_label": "HOL",
        "color": "#9333ea",
    },
)

PLAN_LOCATION_MAP = {opt["value"]: opt for opt in PLAN_LOCATION_OPTIONS}
