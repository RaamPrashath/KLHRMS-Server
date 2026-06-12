from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.procurement.schema import ProcurementPurchaseOrderLineItemPayload
from app.modules.procurement.service import (
    _calculate_purchase_order_totals,
    _coerce_purchase_order_snapshot,
    approve_procurement_requisition,
    get_procurement_purchase_order_download,
    list_procurement_purchase_orders,
)


def test_purchase_order_line_item_rejects_incorrect_total() -> None:
    with pytest.raises(ValueError):
        ProcurementPurchaseOrderLineItemPayload(
            description="Laptop",
            sku="LTP-001",
            quantity=2,
            unitPrice=1000,
            taxPercent=18,
            total=2000,
        )


def test_purchase_order_totals_sum_multiple_line_items() -> None:
    items = [
        ProcurementPurchaseOrderLineItemPayload(
            description="Laptop",
            sku="LTP-001",
            quantity=2,
            unitPrice=1000,
            taxPercent=18,
            total=2360,
        ),
        ProcurementPurchaseOrderLineItemPayload(
            description="Dock",
            sku="DCK-101",
            quantity=1,
            unitPrice=250,
            taxPercent=5,
            total=262.5,
        ),
    ]

    subtotal, tax_total, grand_total = _calculate_purchase_order_totals(items)

    assert subtotal == 2250
    assert tax_total == 372.5
    assert grand_total == 2622.5


def test_legacy_purchase_order_snapshot_is_mapped_to_v1_template_and_document() -> None:
    legacy_snapshot = {
        "company": {
            "name": "Kovan Labs",
            "logoUrl": "https://example.com/logo.png",
            "address": "Chennai",
            "contactEmail": "finance@example.com",
            "contactPhone": "+91 90000 00000",
            "taxId": "GST-123",
        },
        "vendor": {
            "name": "Acme Systems",
            "contactPerson": "Taylor",
            "email": "vendor@example.com",
            "phone": "+91 94444 44444",
            "address": "Bengaluru",
        },
        "document": {
            "purchaseOrderDate": date(2026, 5, 28),
            "deliveryDate": date(2026, 6, 10),
            "paymentTerms": "Net 15",
            "deliveryAddress": "Mumbai",
            "shippingMethod": "Air",
            "currency": "INR",
        },
        "lineItem": {
            "description": "MacBook Pro",
            "sku": "MBP-14",
            "quantity": 1,
            "unitPrice": 180000,
            "taxPercent": 18,
            "total": 212400,
        },
        "notes": {
            "subject": "Replacement device",
            "justification": "For engineering leadership",
            "specificationNotes": "16GB RAM minimum",
            "additionalNotes": "Handle with priority shipping",
        },
        "signatory": {
            "name": "Alex Finance",
            "title": "Finance Manager",
        },
    }

    template, document = _coerce_purchase_order_snapshot(legacy_snapshot)

    assert template is not None
    assert document is not None
    assert template.company.displayName == "Kovan Labs"
    assert document.document.vendor.name == "Acme Systems"
    assert document.lineItems[0].description == "MacBook Pro"
    assert document.document.paymentTermsHtml is not None
    assert document.document.notesHtml is not None


@pytest.mark.asyncio
async def test_list_procurement_purchase_orders_returns_flat_org_rows() -> None:
    requisition = SimpleNamespace(requestNumber=42, id="req-1", assetName="MacBook Pro")
    generated_by = SimpleNamespace(user=SimpleNamespace(name="Alex Finance", email="alex@example.com"))
    recipient = SimpleNamespace(user=SimpleNamespace(name="Jamie Admin", email="jamie@example.com"))
    purchase_order = SimpleNamespace(
        id="po-1",
        poNumber="PO-2026-00001",
        status="GENERATED",
        fileName="po-2026-00001.pdf",
        generatedAt="2026-05-28T10:00:00Z",
        generatedBy=generated_by,
        recipient=recipient,
        recipientEmail="jamie@example.com",
        requisition=requisition,
        storageBucket="procurement-purchase-orders",
        storagePath="org-1/purchase-orders/req-1/po-2026-00001.pdf",
        createdAt="2026-05-28T10:00:00Z",
    )

    class FakeResult:
        def unique(self) -> FakeResult:
            return self

        def scalars(self) -> FakeResult:
            return self

        def all(self) -> list[SimpleNamespace]:
            return [purchase_order]

    class FakeDb:
        async def execute(self, _query: object) -> FakeResult:
            return FakeResult()

    ctx = SimpleNamespace(
        organization=SimpleNamespace(id="org-1"),
        member=SimpleNamespace(role=SimpleNamespace(permissions={"procurement": {"approve": "organization"}})),
    )

    response = await list_procurement_purchase_orders(FakeDb(), ctx)

    assert len(response.items) == 1
    assert response.items[0].poNumber == "PO-2026-00001"
    assert response.items[0].requestLabel == "APR-00042"
    assert response.items[0].assetName == "MacBook Pro"


@pytest.mark.asyncio
async def test_get_procurement_purchase_order_download_returns_signed_url(monkeypatch: pytest.MonkeyPatch) -> None:
    purchase_order = SimpleNamespace(
        fileName="po-2026-00001.pdf",
        storageBucket="procurement-purchase-orders",
        storagePath="org-1/purchase-orders/req-1/po-2026-00001.pdf",
    )

    async def fake_load_purchase_order(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return purchase_order

    async def fake_create_signed_url(**_kwargs: object) -> str:
        return "https://example.com/download.pdf"

    monkeypatch.setattr("app.modules.procurement.service._load_purchase_order", fake_load_purchase_order)
    monkeypatch.setattr("app.modules.procurement.service.create_private_file_signed_url", fake_create_signed_url)

    ctx = SimpleNamespace(
        organization=SimpleNamespace(id="org-1"),
        member=SimpleNamespace(role=SimpleNamespace(permissions={"procurement": {"approve": "organization"}})),
    )

    response = await get_procurement_purchase_order_download(SimpleNamespace(), ctx, "po-1")

    assert response.fileName == "po-2026-00001.pdf"
    assert response.downloadUrl == "https://example.com/download.pdf"
    assert response.expiresInSeconds == 300


@pytest.mark.asyncio
async def test_approve_replacement_requisition_cancels_linked_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    asset = SimpleNamespace(status="IN_MAINTENANCE", units=[])
    ticket = SimpleNamespace(
        id="ticket-1",
        ticketId="AST-101",
        organizationId="org-1",
        status="OPEN",
        asset=asset,
        assetUnitId=None,
    )
    requisition = SimpleNamespace(
        id="req-1",
        organizationId="org-1",
        requestType="REPLACEMENT",
        maintenanceTicketId="ticket-1",
        status="PENDING",
        approvedByMemberId=None,
        approvedAt=None,
        rejectedAt=None,
        reviewerComment=None,
        raisedBy=SimpleNamespace(user=SimpleNamespace(name="Requester", email="requester@example.com")),
    )

    class FakeResult:
        def __init__(self, value: object) -> None:
            self.value = value

        def unique(self) -> FakeResult:
            return self

        def scalar_one_or_none(self) -> object:
            return self.value

    class FakeDb:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.committed = False

        async def execute(self, _query: object) -> FakeResult:
            return FakeResult(ticket)

        def add(self, value: object) -> None:
            self.added.append(value)

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            self.committed = True

    async def fake_load_requisition(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return requisition

    async def fake_get_org(*_args: object, **_kwargs: object) -> None:
        return None

    async def fake_send_decided(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.modules.procurement.service._load_requisition", fake_load_requisition)
    monkeypatch.setattr("app.modules.procurement.service._get_org", fake_get_org)
    monkeypatch.setattr("app.modules.procurement.service.send_procurement_requisition_decided", fake_send_decided)
    monkeypatch.setattr(
        "app.modules.procurement.service._serialize_requisition",
        lambda req, _actor: SimpleNamespace(status=req.status, reviewerComment=req.reviewerComment),
    )

    ctx = SimpleNamespace(
        organization=SimpleNamespace(id="org-1"),
        member=SimpleNamespace(
            id="finance-1",
            role=SimpleNamespace(
                name="Finance Manager",
                permissions={"procurement": {"approve": "organization"}},
            ),
        ),
    )
    payload = SimpleNamespace(comment="Approved for replacement")
    db = FakeDb()

    response = await approve_procurement_requisition(db, ctx, "req-1", payload)

    assert requisition.status == "APPROVED"
    assert ticket.status == "CANCELLED"
    assert asset.status == "DAMAGED"
    assert db.committed is True
    assert response.status == "APPROVED"


@pytest.mark.asyncio
async def test_approve_bulk_requisition_skips_ticket_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    requisition = SimpleNamespace(
        id="req-2",
        organizationId="org-1",
        requestType="BULK",
        maintenanceTicketId=None,
        status="PENDING",
        approvedByMemberId=None,
        approvedAt=None,
        rejectedAt=None,
        reviewerComment=None,
        raisedBy=None,
    )

    class FakeDb:
        def __init__(self) -> None:
            self.committed = False

        async def execute(self, _query: object) -> None:
            raise AssertionError("ticket lookup should not run for bulk requisitions")

        def add(self, _value: object) -> None:
            return None

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            self.committed = True

    async def fake_load_requisition(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return requisition

    async def fake_get_org(*_args: object, **_kwargs: object) -> None:
        return None

    async def fake_send_decided(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.modules.procurement.service._load_requisition", fake_load_requisition)
    monkeypatch.setattr("app.modules.procurement.service._get_org", fake_get_org)
    monkeypatch.setattr("app.modules.procurement.service.send_procurement_requisition_decided", fake_send_decided)
    monkeypatch.setattr(
        "app.modules.procurement.service._serialize_requisition",
        lambda req, _actor: SimpleNamespace(status=req.status),
    )

    ctx = SimpleNamespace(
        organization=SimpleNamespace(id="org-1"),
        member=SimpleNamespace(
            id="finance-1",
            role=SimpleNamespace(
                name="Finance Manager",
                permissions={"procurement": {"approve": "organization"}},
            ),
        ),
    )
    db = FakeDb()

    response = await approve_procurement_requisition(
        db,
        ctx,
        "req-2",
        SimpleNamespace(comment=None),
    )

    assert requisition.status == "APPROVED"
    assert db.committed is True
    assert response.status == "APPROVED"


@pytest.mark.asyncio
async def test_approve_replacement_requisition_keeps_cancelled_ticket_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = SimpleNamespace(status="DAMAGED", units=[])
    ticket = SimpleNamespace(
        id="ticket-3",
        ticketId="AST-303",
        organizationId="org-1",
        status="CANCELLED",
        asset=asset,
        assetUnitId=None,
    )
    requisition = SimpleNamespace(
        id="req-3",
        organizationId="org-1",
        requestType="REPLACEMENT",
        maintenanceTicketId="ticket-3",
        status="PENDING",
        approvedByMemberId=None,
        approvedAt=None,
        rejectedAt=None,
        reviewerComment=None,
        raisedBy=None,
    )

    class FakeResult:
        def __init__(self, value: object) -> None:
            self.value = value

        def unique(self) -> FakeResult:
            return self

        def scalar_one_or_none(self) -> object:
            return self.value

    class FakeDb:
        def __init__(self) -> None:
            self.committed = False

        async def execute(self, _query: object) -> FakeResult:
            return FakeResult(ticket)

        def add(self, _value: object) -> None:
            return None

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            self.committed = True

    async def fake_load_requisition(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return requisition

    async def fake_get_org(*_args: object, **_kwargs: object) -> None:
        return None

    async def fake_send_decided(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.modules.procurement.service._load_requisition", fake_load_requisition)
    monkeypatch.setattr("app.modules.procurement.service._get_org", fake_get_org)
    monkeypatch.setattr("app.modules.procurement.service.send_procurement_requisition_decided", fake_send_decided)
    monkeypatch.setattr(
        "app.modules.procurement.service._serialize_requisition",
        lambda req, _actor: SimpleNamespace(status=req.status),
    )

    ctx = SimpleNamespace(
        organization=SimpleNamespace(id="org-1"),
        member=SimpleNamespace(
            id="finance-1",
            role=SimpleNamespace(
                name="Finance Manager",
                permissions={"procurement": {"approve": "organization"}},
            ),
        ),
    )
    db = FakeDb()

    response = await approve_procurement_requisition(
        db,
        ctx,
        "req-3",
        SimpleNamespace(comment=None),
    )

    assert requisition.status == "APPROVED"
    assert ticket.status == "CANCELLED"
    assert asset.status == "DAMAGED"
    assert db.committed is True
    assert response.status == "APPROVED"
