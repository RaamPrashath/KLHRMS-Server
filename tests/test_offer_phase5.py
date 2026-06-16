from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from app.integrations.email.resend_service import ResendEmailService
from app.models.organization import Organization
from app.models.recruitment import Candidate, JobPosting, JobRequisition, OfferLetter
from app.modules.offers import render as offer_render
from app.modules.offers import storage as offer_storage
from app.modules.offers.render import (
    OfferRenderError,
    render_offer_docx,
    render_offer_html,
)
from app.modules.offers.schema import OfferTemplateUpdateRequest
from app.modules.offers.service import _batch_status_for_counts
from app.modules.offers.storage import (
    offer_storage_path,
    offer_template_asset_storage_path,
    safe_offer_file_name,
)


def _snapshot(html: str) -> dict:
    return {
        "template": {"footerHtml": "<p>Footer</p>"},
        "category": {"id": "category-1", "name": "General", "slug": "general"},
        "sections": [
            {
                "sectionKey": "opening",
                "sectionName": "Opening",
                "order": 1,
                "html": html,
            }
        ],
    }


def _render_defaults(first_name: str = "Asha", last_name: str = "Menon") -> dict:
    requisition = JobRequisition(salaryMin=1200000, salaryMax=1600000, currency="INR")
    return {
        "candidate": Candidate(firstName=first_name, lastName=last_name, email="asha@example.com"),
        "job_posting": JobPosting(id="job-1", title="Product Designer", requisition=requisition),
        "offer_letter": OfferLetter(id="offer-1", currency="INR", salary=1600000, title="Offer"),
        "organization": Organization(id="org-1", name="Kovan Labs", slug="kovan"),
        "generated_date": datetime(2026, 5, 27, tzinfo=UTC),
    }


def test_render_replaces_candidate_names_and_offer_date() -> None:
    html = render_offer_html(
        template_snapshot=_snapshot(
            "<p>Hello {{ candidate.firstName }} {{candidate.lastName}}</p>"
            "<p>{{offer.generatedDate}}</p>"
        ),
        **_render_defaults(),
    )

    assert "Hello Asha Menon" in html
    assert "27 May 2026" in html
    assert "{{candidate" not in html


def test_render_missing_first_name_fails_candidate() -> None:
    with pytest.raises(OfferRenderError, match="Candidate first name is missing"):
        render_offer_html(
            template_snapshot=_snapshot("<p>Hello {{candidate.firstName}}</p>"),
            **_render_defaults(first_name=""),
        )


def test_render_unknown_variable_fails_candidate() -> None:
    with pytest.raises(OfferRenderError, match="Unknown offer variable token"):
        render_offer_html(
            template_snapshot=_snapshot("<p>{{candidate.middleName}}</p>"),
            **_render_defaults(),
        )


def test_render_footer_uses_compact_pdf_spacing() -> None:
    html = render_offer_html(
        template_snapshot={
            "template": {
                "footerHtml": (
                    '<div class="offer-letter-footer">'
                    '<div class="offer-signature-slot"><p class="offer-signature-name">(Mouniesh)</p><p>Intern</p></div>'
                    '<div class="offer-footer-address"><p>Kovan Technology Labs India Private Limited</p><p>Peelamedu</p></div>'
                    '<a class="offer-footer-website" href="https://www.kovanlabs.com">www.kovanlabs.com</a>'
                    "</div>"
                )
            },
            "category": {"id": "category-1", "name": "General", "slug": "general"},
            "sections": [
                {
                    "sectionKey": "opening",
                    "sectionName": "Opening",
                    "order": 1,
                    "html": "<p>Hello {{ candidate.firstName }}</p>",
                }
            ],
        },
        **_render_defaults(),
    )

    assert ".offer-content footer p { margin: 0; line-height: 19px; }" in html
    assert ".offer-signature-slot { grid-column: 1; grid-row: 1; margin: 0 0 12px;" in html
    assert ".offer-signature-slot img { display: block; max-width: 128px; max-height: 80px; object-fit: contain; margin: 0; }" in html
    assert ".offer-signature-name { margin: 0; font-weight: 600; }" in html
    assert ".offer-footer-address p { margin: 0; line-height: 19px; }" in html
    assert ".offer-content .offer-footer-website" in html


def test_render_offer_docx_from_html() -> None:
    docx = render_offer_docx("<html><body><h1>Offer</h1><p>Hello Asha</p></body></html>")

    assert docx.startswith(b"PK")


@pytest.mark.asyncio
async def test_pdf_renderer_inlines_remote_images(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, str] = {}

    class FakeResponse:
        headers = {"content-type": "image/png"}
        content = b"image-bytes"

        def raise_for_status(self) -> None:
            calls["status"] = "ok"

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            calls["client"] = str(kwargs)

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            calls["closed"] = "yes"

        async def get(self, source: str) -> FakeResponse:
            calls["source"] = source
            return FakeResponse()

    monkeypatch.setattr(offer_render.httpx, "AsyncClient", FakeClient)

    html = await offer_render._inline_offer_pdf_images(
        '<img src="https://cdn.example.com/logo.png?token=a&amp;version=1" alt="">'
    )

    assert calls["source"] == "https://cdn.example.com/logo.png?token=a&version=1"
    assert 'src="data:image/png;base64,aW1hZ2UtYnl0ZXM="' in html


@pytest.mark.asyncio
async def test_pdf_renderer_uses_pixel_matched_playwright_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakePage:
        async def emulate_media(self, **kwargs: object) -> None:
            calls["media"] = kwargs

        async def set_content(self, html: str, wait_until: str) -> None:
            calls["html"] = html
            calls["wait_until"] = wait_until

        async def evaluate(self, script: str) -> None:
            calls["evaluate"] = script

        async def pdf(self, **kwargs: object) -> bytes:
            calls["pdf"] = kwargs
            return b"%PDF"

    class FakeBrowser:
        async def new_page(self, **kwargs: object) -> FakePage:
            calls["new_page"] = kwargs
            return FakePage()

        async def close(self) -> None:
            calls["closed"] = True

    class FakeChromium:
        async def launch(self, headless: bool) -> FakeBrowser:
            calls["headless"] = headless
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        async def stop(self) -> None:
            calls["stopped"] = True

    class FakeStarter:
        async def start(self) -> FakePlaywright:
            return FakePlaywright()

    fake_module = types.ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: FakeStarter()
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)

    pdf = await offer_render.render_offer_pdf("<html></html>")

    assert pdf == b"%PDF"
    assert calls["new_page"] == {
        "viewport": {"width": 794, "height": 1123},
        "device_scale_factor": 1,
    }
    assert calls["media"] == {"media": "screen"}
    assert calls["wait_until"] == "networkidle"
    assert "document.fonts.ready" in str(calls["evaluate"])
    assert calls["pdf"] == {
        "width": "794px",
        "height": "1123px",
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
        "print_background": True,
        "prefer_css_page_size": True,
        "scale": 1,
    }
    assert calls["closed"] is True
    assert calls["stopped"] is True


def test_supabase_storage_path_uses_unique_offer_letter_id() -> None:
    file_name = safe_offer_file_name("Asha Menon", "Product Designer")
    path = offer_storage_path(
        organization_id="org-1",
        job_posting_id="job-1",
        application_id="app-1",
        offer_letter_id="offer-1",
        file_name=file_name,
    )

    assert file_name == "Asha Menon - Product Designer Offer Letter.pdf"
    assert path == "org-1/offers/job-1/app-1/offer-1/Asha Menon - Product Designer Offer Letter.pdf"


def test_template_asset_storage_path_uses_offer_bucket_namespace() -> None:
    path = offer_template_asset_storage_path(
        organization_id="org-1",
        template_id="template-1",
        extension=".png",
    )

    assert path.startswith("org-1/offers/templates/template-1/assets/")
    assert path.endswith(".png")
    assert "/uploads/" not in path


def test_template_asset_urls_reject_local_offer_uploads() -> None:
    with pytest.raises(ValueError):
        OfferTemplateUpdateRequest(
            logoUrl="http://localhost:8000/uploads/offers/org/template/logo.png",
        )


@pytest.mark.asyncio
async def test_offer_upload_network_error_is_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, *args: object, **kwargs: object) -> httpx.Response:
            request = httpx.Request("POST", "https://supabase.example/storage/v1/object")
            raise httpx.ConnectError("getaddrinfo failed", request=request)

    monkeypatch.setattr(offer_storage.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        offer_storage,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://supabase.example",
            supabase_service_role_key="service-role-key",
            supabase_offer_bucket="offer-letter",
        ),
    )

    with pytest.raises(RuntimeError, match="Supabase offer upload failed: network error"):
        await offer_storage.upload_offer_file(
            content=b"pdf",
            storage_path="org/offers/test.pdf",
            content_type="application/pdf",
        )


@pytest.mark.asyncio
async def test_offer_email_contains_links_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, str] = {}

    async def fake_send_email(self: ResendEmailService, to_email: str, subject: str, html: str, text: str) -> None:
        sent["to"] = to_email
        sent["subject"] = subject
        sent["html"] = html
        sent["text"] = text

    monkeypatch.setattr(ResendEmailService, "_send_email", fake_send_email)

    await ResendEmailService().send_offer_letter(
        to_email="asha@example.com",
        candidate_name="Asha Menon",
        job_title="Product Designer",
        organization_name="Kovan Labs",
        download_url="https://example.com/download.pdf",
        accept_url="https://example.com/accept",
        reject_url="https://example.com/reject",
        expires_at_text="10 Jun 2026",
    )

    assert sent["to"] == "asha@example.com"
    assert sent["subject"] == "Offer Letter for Product Designer at Kovan Labs"
    assert "https://example.com/download.pdf" in sent["html"]
    assert "https://example.com/accept" in sent["text"]
    assert "10 Jun 2026" in sent["text"]


def test_batch_with_success_and_failure_becomes_partial_failed() -> None:
    assert _batch_status_for_counts(1, 1).value == "PARTIAL_FAILED"
