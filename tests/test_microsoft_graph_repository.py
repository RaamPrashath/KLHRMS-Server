from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.microsoft_graph.schema import MicrosoftUser
from app.modules.microsoft_graph.repository import MicrosoftGraphRepository
from app.models.account import Account
from app.models.member import Member
from app.models.user import User


class FakeResult:
    def __init__(self, value: object | None = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class FakeDb:
    def __init__(self, results: list[object | None]) -> None:
        self._results = list(results)
        self.added: list[object] = []

    async def execute(self, _query: object) -> FakeResult:
        if not self._results:
            return FakeResult(None)
        return FakeResult(self._results.pop(0))

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_upsert_user_member_from_graph_sets_explicit_timestamps() -> None:
    fake_db = FakeDb([None, None, None])
    repository = MicrosoftGraphRepository(fake_db)  # type: ignore[arg-type]
    graph_user = MicrosoftUser(
        graph_id="graph-user-1",
        display_name="Ada Lovelace",
        user_principal_name="ada.lovelace@example.com",
        email="ada.lovelace@example.com",
        employee_id="EMP-001",
        department="Engineering",
        job_title="Engineering Manager",
        account_enabled=True,
    )

    user, member, was_created = await repository.upsert_user_member_from_graph(
        "11111111-1111-1111-1111-111111111111",
        graph_user,
        "role-employee",
    )

    assert was_created is True
    assert isinstance(user, User)
    assert isinstance(member, Member)
    assert len(fake_db.added) == 3

    created_user = next(item for item in fake_db.added if isinstance(item, User))
    created_account = next(item for item in fake_db.added if isinstance(item, Account))
    created_member = next(item for item in fake_db.added if isinstance(item, Member))

    assert created_user.createdAt is not None
    assert created_user.updatedAt is not None
    assert created_account.createdAt is not None
    assert created_account.updatedAt is not None
    assert created_member.createdAt is not None
    assert created_user.email == "ada.lovelace@example.com"
    assert created_member.roleId == "role-employee"
    assert created_member.userId == created_user.id
    assert created_account.userId == created_user.id