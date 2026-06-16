from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.recruitment import (
    CandidateApplication,
    OfferLetter,
    OfferStatus,
    PipelineStage,
    StageType,
)
from app.modules.offers import service
from app.modules.offers.service import accept_offer_by_token, reject_offer_by_token


class FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


class FakeRepository:
    offer: OfferLetter | None = None
    latest_offer: OfferLetter | None = None
    target_stage: PipelineStage | None = None
    histories: list[object] = []

    def __init__(self, db: FakeDb) -> None:
        self.db = db

    async def get_offer_by_token(self, token: str) -> OfferLetter | None:
        return self.offer

    async def get_latest_offer_for_application(
        self,
        organization_id: str,
        application_id: str,
    ) -> OfferLetter | None:
        return self.latest_offer

    async def get_first_stage_by_type(
        self,
        organization_id: str,
        job_posting_id: str,
        stage_type: StageType,
    ) -> PipelineStage | None:
        return self.target_stage if self.target_stage and self.target_stage.stageType == stage_type else None

    async def add_stage_history(self, history: object) -> object:
        self.histories.append(history)
        return history


def _install_fake_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeRepository.offer = None
    FakeRepository.latest_offer = None
    FakeRepository.target_stage = None
    FakeRepository.histories = []
    monkeypatch.setattr(service, "OfferRepository", FakeRepository)


def _application(stage_id: str = "offer-stage") -> CandidateApplication:
    return CandidateApplication(
        id="application-1",
        organizationId="organization-1",
        candidateId="candidate-1",
        jobPostingId="job-1",
        pipelineStageId=stage_id,
    )


def _offer(
    application: CandidateApplication,
    *,
    status: OfferStatus = OfferStatus.SENT,
    expires_at: datetime | None = None,
) -> OfferLetter:
    offer = OfferLetter(
        id="offer-1",
        organizationId="organization-1",
        applicationId=application.id,
        status=status,
        title="Offer",
        currency="INR",
        candidateToken="token",
        expiresAt=expires_at,
    )
    offer.application = application
    return offer


def _stage(stage_type: StageType, stage_id: str) -> PipelineStage:
    return PipelineStage(
        id=stage_id,
        organizationId="organization-1",
        jobPostingId="job-1",
        name=stage_type.value,
        slug=stage_type.value.lower(),
        order=10,
        stageType=stage_type,
    )


def test_public_offer_routes_are_registered() -> None:
    from app.main import app

    route_paths = {route.path for route in app.routes}
    assert "/public/offers/{token}/accept" in route_paths
    assert "/public/offers/{token}/reject" in route_paths
    assert "/public/offers/{token}/download" in route_paths
    assert "/offers/pipeline/jobs/{job_slug}/stages/{stage_slug}/download/validate" in route_paths
    assert "/offers/pipeline/jobs/{job_slug}/stages/{stage_slug}/download" in route_paths


@pytest.mark.asyncio
async def test_accept_offer_moves_to_hired_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_repository(monkeypatch)
    db = FakeDb()
    application = _application()
    offer = _offer(application)
    FakeRepository.offer = offer
    FakeRepository.latest_offer = offer
    FakeRepository.target_stage = _stage(StageType.HIRED, "hired-stage")

    message = await accept_offer_by_token(db, "token")

    assert message == "Offer accepted"
    assert offer.status == OfferStatus.ACCEPTED
    assert application.pipelineStageId == "hired-stage"
    assert len(FakeRepository.histories) == 1
    assert db.committed is True


@pytest.mark.asyncio
async def test_reject_offer_does_not_change_accepted_offer(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_repository(monkeypatch)
    db = FakeDb()
    application = _application()
    offer = _offer(application, status=OfferStatus.ACCEPTED)
    FakeRepository.offer = offer
    FakeRepository.latest_offer = offer
    FakeRepository.target_stage = _stage(StageType.REJECTED, "rejected-stage")

    message = await reject_offer_by_token(db, "token")

    assert message == "Offer already responded"
    assert offer.status == OfferStatus.ACCEPTED
    assert application.pipelineStageId == "offer-stage"
    assert FakeRepository.histories == []


@pytest.mark.asyncio
async def test_expired_offer_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_repository(monkeypatch)
    db = FakeDb()
    application = _application()
    offer = _offer(application, expires_at=datetime.now(UTC) - timedelta(days=1))
    FakeRepository.offer = offer
    FakeRepository.latest_offer = offer
    FakeRepository.target_stage = _stage(StageType.HIRED, "hired-stage")

    message = await accept_offer_by_token(db, "token")

    assert message == "Offer expired"
    assert offer.status == OfferStatus.EXPIRED
    assert application.pipelineStageId == "offer-stage"
    assert FakeRepository.histories == []


@pytest.mark.asyncio
async def test_superseded_offer_is_not_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_repository(monkeypatch)
    db = FakeDb()
    application = _application()
    offer = _offer(application)
    newer_offer = _offer(application)
    newer_offer.id = "offer-2"
    FakeRepository.offer = offer
    FakeRepository.latest_offer = newer_offer
    FakeRepository.target_stage = _stage(StageType.HIRED, "hired-stage")

    message = await accept_offer_by_token(db, "token")

    assert message == "This offer is no longer active"
    assert offer.status == OfferStatus.SENT
    assert application.pipelineStageId == "offer-stage"
    assert FakeRepository.histories == []
