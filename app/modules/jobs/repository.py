from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.department import Department
from app.models.member import Member
from app.models.recruitment import (
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    CandidateResumeAnalysis,
    JobPosting,
    JobPostingStatus,
    JobRequisition,
    JobRequisitionRules,
    JobRequisitionStatus,
    PipelineStage,
    RequisitionActivityLog,
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
        department_ids: list[str] | None = None,
        team_member_ids: list[str] | None = None,
    ) -> list[JobRequisition]:
        query = (
            select(JobRequisition)
            .options(
                joinedload(JobRequisition.organization),
                joinedload(JobRequisition.department),
                joinedload(JobRequisition.raisedBy).joinedload(Member.user),
                joinedload(JobRequisition.replacementFor).joinedload(Member.user),
                selectinload(JobRequisition.approvals)
                .joinedload(RequisitionApproval.approver)
                .joinedload(Member.user),
            )
            .where(JobRequisition.organizationId == organization_id)
            .order_by(JobRequisition.createdAt.desc())
        )
        if raised_by_id is not None:
            query = query.where(JobRequisition.raisedById == raised_by_id)
        if department_ids is not None:
            query = query.where(JobRequisition.departmentId.in_(department_ids))
        if team_member_ids is not None:
            query = query.where(JobRequisition.raisedById.in_(team_member_ids))

        result = await self.db.execute(query)
        return list(result.unique().scalars().all())

    async def list_requisitions_by_statuses(
        self,
        organization_id: str,
        statuses: list[JobRequisitionStatus],
    ) -> list[JobRequisition]:
        query = (
            select(JobRequisition)
            .options(
                joinedload(JobRequisition.organization),
                joinedload(JobRequisition.department),
                joinedload(JobRequisition.raisedBy).joinedload(Member.user),
                joinedload(JobRequisition.replacementFor).joinedload(Member.user),
                selectinload(JobRequisition.approvals)
                .joinedload(RequisitionApproval.approver)
                .joinedload(Member.user),
            )
            .where(
                JobRequisition.organizationId == organization_id,
                JobRequisition.status.in_(statuses),
            )
            .order_by(JobRequisition.createdAt.desc())
        )
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
                joinedload(JobRequisition.organization),
                joinedload(JobRequisition.department),
                joinedload(JobRequisition.raisedBy).joinedload(Member.user),
                joinedload(JobRequisition.replacementFor).joinedload(Member.user),
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

    async def get_requisition_rules(
        self,
        organization_id: str,
        requisition_id: str,
    ) -> JobRequisitionRules | None:
        result = await self.db.execute(
            select(JobRequisitionRules).where(
                JobRequisitionRules.organizationId == organization_id,
                JobRequisitionRules.requisitionId == requisition_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_requisition_rules(
        self,
        rules: JobRequisitionRules,
    ) -> JobRequisitionRules:
        existing = await self.get_requisition_rules(
            rules.organizationId,
            rules.requisitionId,
        )
        if existing is None:
            self.db.add(rules)
            await self.db.flush()
            return rules

        existing.jobPostingId = rules.jobPostingId
        existing.rulesVersion = rules.rulesVersion
        existing.knockoutRules = rules.knockoutRules
        existing.scoringWeights = rules.scoringWeights
        existing.sourceSnapshot = rules.sourceSnapshot
        self.db.add(existing)
        await self.db.flush()
        return existing

    async def create_requisition(self, requisition: JobRequisition) -> JobRequisition:
        self.db.add(requisition)
        await self.db.commit()
        await self.db.refresh(requisition)
        return requisition

    async def get_max_requisition_number(self, organization_id: str) -> int | None:
        result = await self.db.execute(
            select(func.max(JobRequisition.requisitionNumber)).where(
                JobRequisition.organizationId == organization_id,
            )
        )
        return result.scalar()

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
            .where(Member.organizationId == organization_id, Member.status == "ACTIVE")  # status: ACTIVE only
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

    async def get_member(
        self,
        organization_id: str,
        member_id: str,
    ) -> Member | None:
        result = await self.db.execute(
            select(Member).where(
                Member.organizationId == organization_id,
                Member.id == member_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_public_postings(self) -> list[JobPosting]:
        result = await self.db.execute(
            select(JobPosting)
            .options(
                joinedload(JobPosting.organization),
                joinedload(JobPosting.requisition).joinedload(JobRequisition.department),
            )
            .where(JobPosting.status == JobPostingStatus.PUBLISHED)
            .order_by(JobPosting.publishedAt.desc(), JobPosting.createdAt.desc())
        )
        return list(result.unique().scalars().all())

    async def get_public_posting(self, posting_id: str) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting)
            .options(
                joinedload(JobPosting.organization),
                joinedload(JobPosting.requisition).joinedload(JobRequisition.department),
            )
            .where(
                JobPosting.id == posting_id,
                JobPosting.status == JobPostingStatus.PUBLISHED,
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_posting_by_id(self, posting_id: str, organization_id: str) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting)
            .where(
                JobPosting.id == posting_id,
                JobPosting.organizationId == organization_id,
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
                func.lower(Candidate.email) == email.lower(),
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

    async def list_job_postings_for_org(self, organization_id: str) -> list[JobPosting]:
        result = await self.db.execute(
            select(JobPosting).where(JobPosting.organizationId == organization_id)
        )
        return list(result.scalars().all())

    async def count_applications_for_job_posting(
        self,
        organization_id: str,
        job_posting_id: str | None,
    ) -> int:
        if job_posting_id is None:
            return 0
        result = await self.db.execute(
            select(func.count(CandidateApplication.id)).where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.jobPostingId == job_posting_id,
            )
        )
        return int(result.scalar() or 0)

    async def list_resume_analysis_stats_for_job_posting(
        self,
        organization_id: str,
        job_posting_id: str | None,
    ) -> list[tuple[str, int | None, bool]]:
        if job_posting_id is None:
            return []
        result = await self.db.execute(
            select(
                CandidateResumeAnalysis.status,
                CandidateResumeAnalysis.compositeScore,
                CandidateResumeAnalysis.isFlaggedForCheating,
            )
            .join(
                CandidateApplication,
                CandidateApplication.id == CandidateResumeAnalysis.applicationId,
            )
            .where(
                CandidateResumeAnalysis.organizationId == organization_id,
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.jobPostingId == job_posting_id,
            )
        )
        return [(str(status), score, bool(flagged)) for status, score, flagged in result.all()]

    async def list_application_ids_for_job_posting(
        self,
        organization_id: str,
        job_posting_id: str | None,
    ) -> list[str]:
        if job_posting_id is None:
            return []
        result = await self.db.execute(
            select(CandidateApplication.id).where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.jobPostingId == job_posting_id,
            )
        )
        return [str(row[0]) for row in result.all()]

    async def list_resume_analysis_candidates_for_job_posting(
        self,
        organization_id: str,
        job_posting_id: str | None,
    ) -> list[tuple[CandidateApplication, CandidateResumeAnalysis]]:
        if job_posting_id is None:
            return []
        result = await self.db.execute(
            select(CandidateApplication, CandidateResumeAnalysis)
            .join(Candidate, Candidate.id == CandidateApplication.candidateId)
            .join(
                CandidateResumeAnalysis,
                CandidateApplication.id == CandidateResumeAnalysis.applicationId,
            )
            .options(joinedload(CandidateApplication.candidate))
            .where(
                CandidateApplication.organizationId == organization_id,
                Candidate.organizationId == organization_id,
                CandidateResumeAnalysis.organizationId == organization_id,
                CandidateApplication.jobPostingId == job_posting_id,
            )
            .order_by(
                CandidateResumeAnalysis.isFlaggedForCheating.desc(),
                CandidateResumeAnalysis.compositeScore.desc().nullslast(),
                CandidateApplication.appliedAt.desc(),
            )
        )
        return [(application, analysis) for application, analysis in result.unique().all()]

    async def add_pipeline_stages(self, stages: list[PipelineStage]) -> None:
        self.db.add_all(stages)
        await self.db.flush()

    async def get_job_posting_by_requisition(
        self,
        organization_id: str,
        requisition_id: str,
    ) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting)
            .options(
                joinedload(JobPosting.requisition).joinedload(JobRequisition.department),
            )
            .where(
                JobPosting.organizationId == organization_id,
                JobPosting.requisitionId == requisition_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_pipeline_stages(
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
        return list(result.unique().scalars().all())

    async def list_stage_slugs(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> list[str]:
        result = await self.db.execute(
            select(PipelineStage.slug).where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
            )
        )
        return [str(slug) for slug in result.scalars().all()]

    async def create_pipeline_stage(self, stage: PipelineStage) -> PipelineStage:
        self.db.add(stage)
        await self.db.flush()
        return stage

    async def list_job_postings_for_import(
        self,
        organization_id: str,
        exclude_job_posting_id: str,
    ) -> list[JobPosting]:
        result = await self.db.execute(
            select(JobPosting)
            .options(
                joinedload(JobPosting.requisition).joinedload(JobRequisition.department),
                selectinload(JobPosting.pipelineStages),
            )
            .where(
                JobPosting.organizationId == organization_id,
                JobPosting.id != exclude_job_posting_id,
            )
            .order_by(JobPosting.createdAt.desc())
        )
        return list(result.unique().scalars().all())

    async def get_pipeline_stages_for_import(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> list[PipelineStage]:
        return await self.list_pipeline_stages(organization_id, job_posting_id)

    async def delete_pipeline_stages(self, stages: list[PipelineStage]) -> None:
        for stage in stages:
            await self.db.delete(stage)
        await self.db.flush()

    async def add_activity_log(self, log: RequisitionActivityLog) -> RequisitionActivityLog:
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_activity_logs(
        self,
        organization_id: str,
        requisition_id: str,
    ) -> list[RequisitionActivityLog]:
        result = await self.db.execute(
            select(RequisitionActivityLog)
            .options(
                joinedload(RequisitionActivityLog.actor).joinedload(Member.user),
            )
            .where(
                RequisitionActivityLog.organizationId == organization_id,
                RequisitionActivityLog.requisitionId == requisition_id,
            )
            .order_by(RequisitionActivityLog.createdAt.desc())
        )
        return list(result.unique().scalars().all())
