from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.department import Department
from app.models.member import Member
from app.models.recruitment import (
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    JobPosting,
    JobPostingStatus,
    JobRequisition,
    PipelineStage,
    RequisitionApproval,
)
from app.shared.utils.permissions import get_permission_scope


class JobRequisitionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_requisitions(
        self,
        organization_id: str,
        raised_by_id: str | None = None,
    ) -> list[JobRequisition]:
        query = (
            select(JobRequisition)
            .options(
                joinedload(JobRequisition.department),
                joinedload(JobRequisition.raisedBy).joinedload(Member.user),
                selectinload(JobRequisition.approvals)
                .joinedload(RequisitionApproval.approver)
                .joinedload(Member.user),
            )
            .where(JobRequisition.organizationId == organization_id)
            .order_by(JobRequisition.createdAt.desc())
        )
        if raised_by_id is not None:
            query = query.where(JobRequisition.raisedById == raised_by_id)

        result = await self.db.execute(query)
        return list(result.unique().scalars().all())

    async def get_requisition(
        self,
        organization_id: str,
        requisition_id: str,
    ) -> JobRequisition | None:
        result = await self.db.execute(
            select(JobRequisition)
            .options(
                joinedload(JobRequisition.department),
                joinedload(JobRequisition.raisedBy).joinedload(Member.user),
                selectinload(JobRequisition.approvals)
                .joinedload(RequisitionApproval.approver)
                .joinedload(Member.user),
            )
            .where(
                JobRequisition.organizationId == organization_id,
                JobRequisition.id == requisition_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def create_requisition(self, requisition: JobRequisition) -> JobRequisition:
        self.db.add(requisition)
        await self.db.commit()
        await self.db.refresh(requisition)
        return requisition

    async def save(self, requisition: JobRequisition) -> JobRequisition:
        self.db.add(requisition)
        await self.db.commit()
        await self.db.refresh(requisition)
        return requisition

    async def create_approvals(self, approvals: list[RequisitionApproval]) -> None:
        self.db.add_all(approvals)
        await self.db.commit()

    async def list_org_approvers(self, organization_id: str) -> list[Member]:
        result = await self.db.execute(
            select(Member)
            .options(joinedload(Member.role), joinedload(Member.user))
            .where(Member.organizationId == organization_id)
        )
        members = list(result.unique().scalars().all())
        return [
            member
            for member in members
            if member.role is not None
            and get_permission_scope(member.role.permissions, "jobs", "approve") == "organization"
        ]

    async def get_department(
        self,
        organization_id: str,
        department_id: str,
    ) -> Department | None:
        result = await self.db.execute(
            select(Department).where(
                Department.organizationId == organization_id,
                Department.id == department_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_public_postings(self) -> list[JobPosting]:
        result = await self.db.execute(
            select(JobPosting)
            .options(joinedload(JobPosting.organization))
            .where(JobPosting.status == JobPostingStatus.PUBLISHED)
            .order_by(JobPosting.publishedAt.desc(), JobPosting.createdAt.desc())
        )
        return list(result.unique().scalars().all())

    async def get_public_posting(self, posting_id: str) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting)
            .options(joinedload(JobPosting.organization))
            .where(
                JobPosting.id == posting_id,
                JobPosting.status == JobPostingStatus.PUBLISHED,
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_matching_requisition_for_posting(
        self,
        organization_id: str,
        title: str,
    ) -> JobRequisition | None:
        result = await self.db.execute(
            select(JobRequisition)
            .options(joinedload(JobRequisition.department))
            .where(
                JobRequisition.organizationId == organization_id,
                JobRequisition.title == title,
            )
            .order_by(JobRequisition.updatedAt.desc(), JobRequisition.createdAt.desc())
        )
        return result.scalars().first()

    async def get_candidate_by_email(
        self,
        organization_id: str,
        email: str,
    ) -> Candidate | None:
        result = await self.db.execute(
            select(Candidate).where(
                Candidate.organizationId == organization_id,
                Candidate.email == email,
            )
        )
        return result.scalar_one_or_none()

    async def get_default_pipeline_stage(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> PipelineStage | None:
        default_result = await self.db.execute(
            select(PipelineStage)
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.isDefault.is_(True),
            )
            .order_by(PipelineStage.order.asc())
        )
        stage = default_result.scalars().first()
        if stage is not None:
            return stage

        result = await self.db.execute(
            select(PipelineStage)
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
            )
            .order_by(PipelineStage.order.asc())
        )
        return result.scalars().first()

    async def get_candidate_application(
        self,
        organization_id: str,
        candidate_id: str,
        job_posting_id: str,
    ) -> CandidateApplication | None:
        result = await self.db.execute(
            select(CandidateApplication).where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.candidateId == candidate_id,
                CandidateApplication.jobPostingId == job_posting_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_candidate(self, candidate: Candidate) -> Candidate:
        self.db.add(candidate)
        await self.db.flush()
        return candidate

    async def add_application(self, application: CandidateApplication) -> CandidateApplication:
        self.db.add(application)
        await self.db.flush()
        return application

    async def add_stage_history(self, history: ApplicationStageHistory) -> ApplicationStageHistory:
        self.db.add(history)
        await self.db.flush()
        return history

    async def add_job_posting(self, posting: JobPosting) -> JobPosting:
        self.db.add(posting)
        await self.db.flush()
        return posting

    async def add_pipeline_stages(self, stages: list[PipelineStage]) -> None:
        self.db.add_all(stages)
        await self.db.flush()
