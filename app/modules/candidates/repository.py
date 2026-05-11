from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.member import Member
from app.models.recruitment import (
    ApplicationStageHistory,
    CandidateApplication,
    JobPosting,
    PipelineStage,
    StageEvaluationCategory,
    StageEvaluationWorkspace,
    StageEvent,
)


class CandidatePipelineRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_job_postings(self, organization_id: str) -> list[JobPosting]:
        result = await self.db.execute(
            select(JobPosting)
            .where(JobPosting.organizationId == organization_id)
            .order_by(JobPosting.createdAt.desc())
        )
        return list(result.scalars().all())

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

    async def list_stages_for_job(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> list[PipelineStage]:
        result = await self.db.execute(
            select(PipelineStage)
            .options(
                selectinload(PipelineStage.applications).joinedload(
                    CandidateApplication.candidate
                ),
                selectinload(PipelineStage.applications).selectinload(
                    CandidateApplication.stageEvents
                ),
                selectinload(PipelineStage.evaluationCategories),
                selectinload(PipelineStage.evaluationWorkspace),
            )
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
            )
            .order_by(PipelineStage.order.asc())
        )
        return list(result.unique().scalars().all())

    async def get_stage(
        self,
        organization_id: str,
        stage_id: str,
    ) -> PipelineStage | None:
        result = await self.db.execute(
            select(PipelineStage)
            .options(
                selectinload(PipelineStage.evaluationCategories),
                selectinload(PipelineStage.evaluationWorkspace),
                selectinload(PipelineStage.applications).joinedload(
                    CandidateApplication.candidate
                ),
                joinedload(PipelineStage.jobPosting),
            )
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.id == stage_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_stage_categories(
        self,
        organization_id: str,
        stage_id: str,
    ) -> list[StageEvaluationCategory]:
        result = await self.db.execute(
            select(StageEvaluationCategory)
            .where(
                StageEvaluationCategory.organizationId == organization_id,
                StageEvaluationCategory.stageId == stage_id,
            )
            .order_by(StageEvaluationCategory.order.asc())
        )
        return list(result.scalars().all())

    async def get_application(
        self,
        organization_id: str,
        application_id: str,
    ) -> CandidateApplication | None:
        result = await self.db.execute(
            select(CandidateApplication)
            .options(
                joinedload(CandidateApplication.candidate),
                joinedload(CandidateApplication.jobPosting),
                joinedload(CandidateApplication.pipelineStage),
                selectinload(CandidateApplication.stageEvents),
            )
            .where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.id == application_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_application_detail(
        self,
        organization_id: str,
        application_id: str,
    ) -> CandidateApplication | None:
        result = await self.db.execute(
            select(CandidateApplication)
            .options(
                joinedload(CandidateApplication.candidate),
                joinedload(CandidateApplication.jobPosting),
                joinedload(CandidateApplication.pipelineStage),
                selectinload(CandidateApplication.stageHistory).options(
                    joinedload(ApplicationStageHistory.fromStage),
                    joinedload(ApplicationStageHistory.toStage),
                    joinedload(ApplicationStageHistory.movedBy).joinedload(Member.user),
                ),
            )
            .where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.id == application_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def count_stage_applications(
        self,
        organization_id: str,
        stage_id: str,
    ) -> int:
        result = await self.db.execute(
            select(func.count(CandidateApplication.id)).where(
                CandidateApplication.organizationId == organization_id,
                CandidateApplication.pipelineStageId == stage_id,
            )
        )
        return int(result.scalar_one())

    async def count_stage_history(
        self,
        organization_id: str,
        stage_id: str,
    ) -> int:
        result = await self.db.execute(
            select(func.count(ApplicationStageHistory.id)).where(
                ApplicationStageHistory.organizationId == organization_id,
                (
                    (ApplicationStageHistory.fromStageId == stage_id)
                    | (ApplicationStageHistory.toStageId == stage_id)
                ),
            )
        )
        return int(result.scalar_one())

    async def add_stage(self, stage: PipelineStage) -> PipelineStage:
        self.db.add(stage)
        await self.db.flush()
        return stage

    async def add_history(
        self,
        history: ApplicationStageHistory,
    ) -> ApplicationStageHistory:
        self.db.add(history)
        await self.db.flush()
        return history

    async def get_evaluation_workspace(
        self,
        organization_id: str,
        stage_id: str,
    ) -> StageEvaluationWorkspace | None:
        result = await self.db.execute(
            select(StageEvaluationWorkspace).where(
                StageEvaluationWorkspace.organizationId == organization_id,
                StageEvaluationWorkspace.stageId == stage_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_any_evaluation_workspace_for_job(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> StageEvaluationWorkspace | None:
        result = await self.db.execute(
            select(StageEvaluationWorkspace)
            .join(PipelineStage, StageEvaluationWorkspace.stageId == PipelineStage.id)
            .where(
                StageEvaluationWorkspace.organizationId == organization_id,
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.evaluationEnabled.is_(True),
            )
            .order_by(StageEvaluationWorkspace.createdAt.asc())
        )
        return result.scalars().first()

    async def list_evaluation_stages_for_job(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> list[PipelineStage]:
        result = await self.db.execute(
            select(PipelineStage)
            .options(
                selectinload(PipelineStage.applications).joinedload(
                    CandidateApplication.candidate
                ),
                selectinload(PipelineStage.evaluationCategories),
                selectinload(PipelineStage.evaluationWorkspace),
            )
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.evaluationEnabled.is_(True),
            )
            .order_by(PipelineStage.order.asc())
        )
        return list(result.unique().scalars().all())

    async def add_evaluation_workspace(
        self,
        workspace: StageEvaluationWorkspace,
    ) -> StageEvaluationWorkspace:
        self.db.add(workspace)
        await self.db.flush()
        return workspace

    async def add_stage_event(self, event: StageEvent) -> StageEvent:
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_latest_stage_event(
        self,
        organization_id: str,
        application_id: str,
        stage_id: str,
    ) -> StageEvent | None:
        result = await self.db.execute(
            select(StageEvent)
            .where(
                StageEvent.organizationId == organization_id,
                StageEvent.applicationId == application_id,
                StageEvent.stageId == stage_id,
            )
            .order_by(StageEvent.createdAt.desc())
        )
        return result.scalars().first()

    async def get_stage_event(
        self,
        organization_id: str,
        application_id: str,
        event_id: str,
    ) -> StageEvent | None:
        result = await self.db.execute(
            select(StageEvent).where(
                StageEvent.organizationId == organization_id,
                StageEvent.applicationId == application_id,
                StageEvent.id == event_id,
            )
        )
        return result.scalars().first()
