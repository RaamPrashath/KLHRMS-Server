from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.modules.assets.service import withdraw_helpdesk_ticket


class FakeResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def unique(self) -> "FakeResult":
        return self

    def scalar_one_or_none(self) -> object:
        return self.value

    def scalar_one(self) -> object:
        return self.value


class FakeDb:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.executed_queries: list[object] = []
        self.committed = False

    async def execute(self, query: object) -> FakeResult:
        self.executed_queries.append(query)
        if not self.results:
            raise AssertionError("Unexpected database execute call")
        return FakeResult(self.results.pop(0))

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_withdraw_helpdesk_ticket_refreshes_response_after_commit() -> None:
    stale_asset = SimpleNamespace(
        name="Old Laptop",
        assetCode="OLD-001",
        status="AVAILABLE",
        provisions=[],
        units=[],
    )
    fresh_asset = SimpleNamespace(
        name="Fresh Laptop",
        assetCode="NEW-001",
        status="AVAILABLE",
        provisions=[],
        units=[],
    )
    ticket = SimpleNamespace(
        id="ticket-1",
        ticketId="#123456",
        organizationId="org-1",
        loggedByMemberId="member-1",
        cancelledByMemberId=None,
        status="OPEN",
        asset=stale_asset,
        assetId="asset-1",
        assetUnitId=None,
        category=None,
        subject="Need help",
        attachmentsMetadata=[],
        maintenanceType="REPAIR",
        issueDescription="Need help with my laptop",
        serviceDate=date(2026, 6, 1),
        createdAt=datetime(2026, 6, 1, 9, 30),
        updatedAt=datetime(2026, 6, 1, 9, 45),
    )
    refreshed_ticket = SimpleNamespace(
        id=ticket.id,
        ticketId=ticket.ticketId,
        ticketMode="ASSET_ISSUE",
        organizationId=ticket.organizationId,
        loggedByMemberId=ticket.loggedByMemberId,
        status="CANCELLED",
        asset=fresh_asset,
        assetId=ticket.assetId,
        assetUnitId=ticket.assetUnitId,
        category=ticket.category,
        subject=ticket.subject,
        attachmentsMetadata=ticket.attachmentsMetadata,
        maintenanceType=ticket.maintenanceType,
        issueDescription=ticket.issueDescription,
        serviceDate=ticket.serviceDate,
        createdAt=ticket.createdAt,
        updatedAt=ticket.updatedAt,
    )

    ctx = SimpleNamespace(
        organization=SimpleNamespace(id="org-1", slug="org"),
        member=SimpleNamespace(id="member-1"),
    )
    db = FakeDb([ticket, None, refreshed_ticket])

    response = await withdraw_helpdesk_ticket(db, ctx, ticket.id)

    assert db.committed is True
    assert len(db.executed_queries) == 3
    assert ticket.cancelledByMemberId == "member-1"
    assert response.status == "CANCELLED"
    assert response.assetName == "Fresh Laptop"
    assert response.assetCode == "NEW-001"