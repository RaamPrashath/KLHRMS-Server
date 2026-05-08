"""Pydantic schemas for the holiday sync module."""

from __future__ import annotations

from pydantic import BaseModel


class HolidaySyncResponse(BaseModel):
    """Response returned by the manual sync endpoint."""

    year: int
    organization_id: str
    rows_inserted: int
    source: str  # "api" | "master"

    model_config = {"populate_by_name": True}
