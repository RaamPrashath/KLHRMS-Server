from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.employee.schema import EmployeeListFilters
from app.modules.employee.service import list_employees


class FakeScalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class FakeResult:
    def __init__(self, scalar_one_or_none_value: object | None = None, rows: list[object] | None = None) -> None:
        self._scalar_one_or_none_value = scalar_one_or_none_value
        self._rows = rows or []

    def scalar_one_or_none(self) -> object | None:
        return self._scalar_one_or_none_value

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._rows)


class FakeDb:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, _query: object) -> FakeResult:
        self.calls += 1
        if self.calls == 1:
            return FakeResult(
                SimpleNamespace(
                    tenant_id="tenant-1",
                    client_id="client-1",
                    client_secret_ciphertext="ciphertext",
                    is_enabled=True,
                )
            )
        return FakeResult(rows=[SimpleNamespace(id="role-employee", name="Employee")])


class FakeGraphClient:
    async def get_users(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                graph_id="graph-user-1",
                display_name="Ada Lovelace",
                email=None,
                user_principal_name="ada.lovelace@example.com",
                account_enabled=True,
            )
        ]


@pytest.mark.asyncio
async def test_list_employees_uses_user_principal_name_when_mail_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.employee.service.TokenManager", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "app.modules.employee.service.MicrosoftGraphClient",
        lambda _token_manager: FakeGraphClient(),
    )

    response = await list_employees(
        "11111111-1111-1111-1111-111111111111",
        EmployeeListFilters(page=1, page_size=25),
        FakeDb(),
    )

    assert response.total == 1
    assert response.items[0].email == "ada.lovelace@example.com"
    assert response.items[0].name == "Ada Lovelace"