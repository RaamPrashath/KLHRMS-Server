from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.employee.service import list_employees


class FakeScalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class FakeResult:
    def __init__(self, rows: list[object] | None = None) -> None:
        self._rows = rows or []

    def all(self) -> list[object]:
        return self._rows

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._rows)

    def __iter__(self) -> Iterator[object]:
        return iter(self._rows)


class FakeDb:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, _query: object) -> FakeResult:
        self.calls += 1
        if self.calls == 1:
            return FakeResult(
                [
                    (
                        SimpleNamespace(
                            id="member-1",
                            createdAt=datetime(2026, 1, 2, 9, 0, 0),
                        ),
                        SimpleNamespace(
                            id="user-1",
                            name=None,
                            email=None,
                            image=None,
                        ),
                        SimpleNamespace(id="role-employee", name="Employee"),
                        SimpleNamespace(
                            display_name="Ada Lovelace",
                            email=None,
                            user_principal_name="ada.lovelace@example.com",
                            profile_photo_url=None,
                            employee_id="EMP-001",
                            department_name="Engineering",
                            job_title="Engineering Manager",
                        ),
                    )
                ]
            )
        if self.calls == 2:
            return FakeResult([])
        return FakeResult([("user-1",)])


@pytest.mark.asyncio
async def test_list_employees_uses_user_principal_name_when_mail_is_missing() -> None:
    response = await list_employees(
        organization_id="11111111-1111-1111-1111-111111111111",
        db=FakeDb(),
    )

    assert response.total == 1
    assert response.items[0].email == "ada.lovelace@example.com"
    assert response.items[0].name == "Ada Lovelace"
    assert response.items[0].microsoft_synced is True
