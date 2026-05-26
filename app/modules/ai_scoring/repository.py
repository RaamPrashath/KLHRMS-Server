from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.recruitment import (
    CandidateApplication,
    CandidateResumeAnalysis,
    JobPosting,
    JobRequisitionRules,
)


class ResumeAnalysisRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_application(
        self,
        organization_id: str,
        application_id: str,
    ) -> CandidateApplication | None:
        result = await self.db.execute(
            select(CandidateApplication)
            .options(joinedload(CandidateApplication.candidate))
            .options(joinedload(CandidateApplication.jobPosting))
            .where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.id == application_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_rules_for_application(
        self,
        organization_id: str,
        application_id: str,
    ) -> JobRequisitionRules | None:
        result = await self.db.execute(
            select(JobRequisitionRules)
            .join(
                JobPosting,
                JobPosting.requisitionId == JobRequisitionRules.requisitionId,
            )
            .join(
                CandidateApplication,
                CandidateApplication.jobPostingId == JobPosting.id,
            )
            .where(
                JobRequisitionRules.organizationId == organization_id,
                JobPosting.organizationId == organization_id,
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.id == application_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_analysis(
        self,
        organization_id: str,
        application_id: str,
    ) -> CandidateResumeAnalysis | None:
        result = await self.db.execute(
            select(CandidateResumeAnalysis).where(
                CandidateResumeAnalysis.organizationId == organization_id,
                CandidateResumeAnalysis.applicationId == application_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_pending_analysis(
        self,
        organization_id: str,
        application_id: str,
        resume_url: str | None,
    ) -> CandidateResumeAnalysis:
        existing = await self.get_analysis(organization_id, application_id)
        if existing is not None:
            existing.resumeUrl = resume_url
            if existing.status in {"FAILED", "UNSUPPORTED"}:
                existing.status = "PENDING"
                existing.lastError = None
            self.db.add(existing)
            await self.db.flush()
            return existing

        analysis = CandidateResumeAnalysis(
            organizationId=organization_id,
            applicationId=application_id,
            status="PENDING",
            resumeUrl=resume_url,
            firewallFlags=[],
            removedSuspiciousText=[],
            parserWarnings=[],
            attemptCount=0,
            isFlaggedForCheating=False,
        )
        self.db.add(analysis)
        await self.db.flush()
        return analysis
