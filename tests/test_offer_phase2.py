import pytest

from app.main import app
from app.models.recruitment import Candidate, CandidateApplication, OfferLetter, OfferStatus
from app.modules.offers.schema import OfferTemplateSectionUpsertRequest
from app.modules.offers.service import _candidate_eligibility, _offer_status


def test_offer_router_is_registered() -> None:
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/offers/templates" in route_paths
    assert "/offers/pipeline/jobs/{job_slug}/stages/{stage_slug}/workspace" in route_paths


def test_section_upsert_request_sanitizes_html_and_rejects_unknown_variables() -> None:
    request = OfferTemplateSectionUpsertRequest(
        sectionName="Opening",
        order=1,
        tiptapJson={},
        html='<p>Hello {{candidate.firstName}}</p><script>alert("x")</script>',
    )

    assert request.html == "<p>Hello {{candidate.firstName}}</p>"

    with pytest.raises(ValueError):
        OfferTemplateSectionUpsertRequest(
            sectionName="Opening",
            order=1,
            tiptapJson={},
            html="<p>{{candidate.middleName}}</p>",
        )


def test_offer_status_maps_email_error_to_failed() -> None:
    offer = OfferLetter(status=OfferStatus.SENT, emailError="SMTP failed")

    assert _offer_status(offer) == "FAILED"


def test_candidate_eligibility_blocks_missing_email_and_names() -> None:
    application = CandidateApplication(
        id="app-1",
        candidate=Candidate(firstName="", lastName="", email=""),
    )

    eligibility = _candidate_eligibility(
        application,
        latest_offer=None,
        requires_compensation=False,
        job_has_salary_data=True,
    )

    assert not eligibility.canSend
    assert "Candidate email is missing" in eligibility.errors
    assert "Candidate first name is missing" in eligibility.errors
    assert "Candidate last name is missing" in eligibility.errors


def test_candidate_eligibility_keeps_resend_selectable_with_warning() -> None:
    application = CandidateApplication(
        id="app-1",
        candidate=Candidate(firstName="Asha", lastName="Rao", email="asha@example.com"),
    )
    offer = OfferLetter(status=OfferStatus.SENT)

    eligibility = _candidate_eligibility(
        application,
        latest_offer=offer,
        requires_compensation=False,
        job_has_salary_data=True,
    )

    assert eligibility.canSend
    assert eligibility.warnings == []


def test_candidate_eligibility_blocks_missing_salary_for_compensation_tokens() -> None:
    application = CandidateApplication(
        id="app-1",
        candidate=Candidate(firstName="Asha", lastName="Rao", email="asha@example.com"),
    )

    eligibility = _candidate_eligibility(
        application,
        latest_offer=None,
        requires_compensation=True,
        job_has_salary_data=False,
    )

    assert not eligibility.canSend
    assert eligibility.errors == ["Job salary data is missing"]
