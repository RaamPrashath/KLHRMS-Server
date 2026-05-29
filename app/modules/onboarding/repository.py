from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.recruitment import (
    CandidateApplication,
    JobPosting,
    OnboardingRecord,
    OnboardingStatus,
    PipelineStage,
    StageType,
)


class OnboardingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_job_by_slug(
        self,
        organization_id: str,
        job_slug: str,
    ) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting)
            .options(joinedload(JobPosting.requisition))
            .where(
                JobPosting.organizationId == organization_id,
                JobPosting.slug == job_slug,
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_stages_for_job(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> list[PipelineStage]:
        result = await self.db.execute(
            select(PipelineStage)
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
            )
            .order_by(PipelineStage.order.asc())
        )
        return list(result.scalars().all())

    async def get_stage_by_job_and_slug(
        self,
        organization_id: str,
        job_posting_id: str,
        stage_slug: str,
    ) -> PipelineStage | None:
        result = await self.db.execute(
            select(PipelineStage).where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.slug == stage_slug,
            )
        )
        return result.scalar_one_or_none()

    async def list_applications_for_stage(
        self,
        organization_id: str,
        stage_id: str,
    ) -> list[CandidateApplication]:
        result = await self.db.execute(
            select(CandidateApplication)
            .options(joinedload(CandidateApplication.candidate))
            .where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.pipelineStageId == stage_id,
            )
            .order_by(CandidateApplication.appliedAt.desc())
        )
        return list(result.unique().scalars().all())

    async def list_applications_by_ids(
        self,
        organization_id: str,
        application_ids: list[str],
    ) -> list[CandidateApplication]:
        if not application_ids:
            return []
        result = await self.db.execute(
            select(CandidateApplication)
            .options(joinedload(CandidateApplication.candidate))
            .where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.id.in_(application_ids),
            )
        )
        return list(result.unique().scalars().all())

    async def get_onboarding_by_application(
        self,
        organization_id: str,
        application_id: str,
    ) -> OnboardingRecord | None:
        result = await self.db.execute(
            select(OnboardingRecord)
            .options(joinedload(OnboardingRecord.application).joinedload(CandidateApplication.candidate))
            .where(
                OnboardingRecord.organizationId == organization_id,
                OnboardingRecord.applicationId == application_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_onboarding_for_applications(
        self,
        organization_id: str,
        application_ids: list[str],
    ) -> dict[str, OnboardingRecord]:
        if not application_ids:
            return {}
        result = await self.db.execute(
            select(OnboardingRecord)
            .where(
                OnboardingRecord.organizationId == organization_id,
                OnboardingRecord.applicationId.in_(application_ids),
            )
        )
        latest: dict[str, OnboardingRecord] = {}
        for record in result.scalars().all():
            if record.applicationId not in latest:
                latest[record.applicationId] = record
        return latest

    async def get_onboarding_by_token(self, token: str) -> OnboardingRecord | None:
        result = await self.db.execute(
            select(OnboardingRecord)
            .options(
                joinedload(OnboardingRecord.application)
                .joinedload(CandidateApplication.candidate),
                joinedload(OnboardingRecord.application)
                .joinedload(CandidateApplication.jobPosting)
                .joinedload(JobPosting.organization),
            )
            .where(OnboardingRecord.candidateToken == token)
        )
        return result.unique().scalar_one_or_none()

    async def get_first_stage_by_type(
        self,
        organization_id: str,
        job_posting_id: str,
        stage_type: StageType,
    ) -> PipelineStage | None:
        result = await self.db.execute(
            select(PipelineStage)
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.stageType == stage_type,
            )
            .order_by(PipelineStage.order.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_job_posting(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting).where(
                JobPosting.organizationId == organization_id,
                JobPosting.id == job_posting_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, item: object) -> None:
        self.db.add(item)
        await self.db.flush()

    async def add_all(self, items: list[object]) -> None:
        self.db.add_all(items)
        await self.db.flush()
