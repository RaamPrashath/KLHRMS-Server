"""Common filter helpers for list endpoints."""
from datetime import date
from typing import Annotated

from fastapi import Query


class DateRangeFilter:
    def __init__(
        self,
        from_date: Annotated[date | None, Query(alias="from")] = None,
        to_date: Annotated[date | None, Query(alias="to")] = None,
    ) -> None:
        self.from_date = from_date
        self.to_date = to_date
