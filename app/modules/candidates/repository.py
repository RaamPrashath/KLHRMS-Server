from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.models.department import Department
from app.models.department_member import DepartmentMember
from app.models.leave import Holiday, LeaveRequest
from app.models.member import Member
from app.models.recruitment import (
    ApplicationStageHistory,
    CandidateApplication,
    HiringTeam,
    HiringTeamMember,
    JobPosting,
    PipelineStage,
    StageEvaluationCategory,
    StageEvaluationWorkspace,
    StageEvent,
    StageEventParticipant,
)
from app.models.user import User


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

    async def get_job_posting_by_slug(
        self,
        organization_id: str,
        slug: str,
    ) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting).where(
                JobPosting.organizationId == organization_id,
                JobPosting.slug == slug,
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
                    CandidateApplication.stageHistory
                ),
                selectinload(PipelineStage.applications).selectinload(
                    CandidateApplication.stageEvents
                ).selectinload(StageEvent.createdBy)
                .joinedload(Member.user),
                selectinload(PipelineStage.applications).selectinload(
                    CandidateApplication.stageEvents
                ).selectinload(StageEvent.completedBy)
                .joinedload(Member.user),
                selectinload(PipelineStage.applications).selectinload(
                    CandidateApplication.stageEvents
                ).selectinload(StageEvent.participants)
                .joinedload(StageEventParticipant.member)
                .joinedload(Member.user),
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

    async def list_stage_slugs(self, organization_id: str, job_posting_id: str) -> list[str]:
        result = await self.db.execute(
            select(PipelineStage.slug).where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
            )
        )
        return [str(slug) for slug in result.scalars().all()]

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

    async def get_stage_by_slug(
        self,
        organization_id: str,
        stage_slug: str,
    ) -> PipelineStage | None:
        result = await self.db.execute(
            select(PipelineStage)
            .options(
                selectinload(PipelineStage.applications).options(
                    joinedload(CandidateApplication.candidate),
                    joinedload(CandidateApplication.jobPosting),
                    selectinload(CandidateApplication.stageEvents)
                    .selectinload(StageEvent.participants)
                    .joinedload(StageEventParticipant.member)
                    .joinedload(Member.user),
                ),
                selectinload(PipelineStage.evaluationCategories),
                selectinload(PipelineStage.evaluationWorkspace),
                joinedload(PipelineStage.jobPosting),
            )
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.slug == stage_slug,
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_stage_by_job_and_slug(
        self,
        organization_id: str,
        job_posting_id: str,
        stage_slug: str,
    ) -> PipelineStage | None:
        result = await self.db.execute(
            select(PipelineStage)
            .options(
                selectinload(PipelineStage.applications).options(
                    joinedload(CandidateApplication.candidate),
                    joinedload(CandidateApplication.jobPosting),
                    selectinload(CandidateApplication.stageHistory),
                    selectinload(CandidateApplication.stageEvents)
                    .selectinload(StageEvent.participants)
                    .joinedload(StageEventParticipant.member)
                    .joinedload(Member.user),
                ),
                selectinload(PipelineStage.evaluationCategories),
                selectinload(PipelineStage.evaluationWorkspace),
                joinedload(PipelineStage.jobPosting),
            )
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.slug == stage_slug,
            )
        )
        return result.unique().scalar_one_or_none()

    async def search_interviewers(
        self,
        organization_id: str,
        search: str | None,
        limit: int = 20,
    ) -> list[tuple[Member, str | None]]:
        query = (
            select(Member, func.min(Department.name))
            .join(User, Member.userId == User.id)
            .options(contains_eager(Member.user))
            .outerjoin(DepartmentMember, DepartmentMember.memberId == Member.id)
            .outerjoin(Department, Department.id == DepartmentMember.departmentId)
            .where(Member.organizationId == organization_id)
            .group_by(Member.id, User.id)
            .order_by(User.name.asc().nullslast(), User.email.asc())
            .limit(limit)
        )
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    func.lower(User.name).like(func.lower(term)),
                    func.lower(User.email).like(func.lower(term)),
                )
            )
        result = await self.db.execute(query)
        return [(member, department) for member, department in result.all()]

    async def get_members_by_ids(
        self,
        organization_id: str,
        member_ids: list[str],
    ) -> list[Member]:
        if not member_ids:
            return []
        result = await self.db.execute(
            select(Member)
            .options(joinedload(Member.user))
            .where(
                Member.organizationId == organization_id,
                Member.id.in_(member_ids),
            )
        )
        return list(result.unique().scalars().all())

    async def list_approved_leave_for_members(
        self,
        organization_id: str,
        member_ids: list[str],
        target_dates: list[date],
    ) -> list[LeaveRequest]:
        if not member_ids or not target_dates:
            return []
        result = await self.db.execute(
            select(LeaveRequest).where(
                LeaveRequest.organizationId == organization_id,
                LeaveRequest.memberId.in_(member_ids),
                LeaveRequest.status == "APPROVED",
                LeaveRequest.deletedAt.is_(None),
                or_(
                    *[
                        and_(
                            LeaveRequest.startDate <= target_date,
                            LeaveRequest.endDate >= target_date,
                        )
                        for target_date in target_dates
                    ]
                ),
            )
        )
        return list(result.scalars().all())

    async def list_holidays(
        self,
        organization_id: str,
        target_dates: list[date],
    ) -> list[Holiday]:
        if not target_dates:
            return []
        result = await self.db.execute(
            select(Holiday).where(
                Holiday.organizationId == organization_id,
                Holiday.holidayDate.in_(target_dates),
                Holiday.isHoliday.is_(True),
                Holiday.deletedAt.is_(None),
            )
        )
        return list(result.scalars().all())

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
                selectinload(CandidateApplication.stageEvents)
                .selectinload(StageEvent.participants),
                selectinload(CandidateApplication.stageHistory),
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
                selectinload(CandidateApplication.stageEvents)
                .selectinload(StageEvent.participants)
                .joinedload(StageEventParticipant.member)
                .joinedload(Member.user),
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

    async def add_stage_event_participant(
        self,
        participant: StageEventParticipant,
    ) -> StageEventParticipant:
        self.db.add(participant)
        await self.db.flush()
        return participant

    async def get_latest_stage_event(
        self,
        organization_id: str,
        application_id: str,
        stage_id: str,
    ) -> StageEvent | None:
        result = await self.db.execute(
            select(StageEvent)
            .options(
                selectinload(StageEvent.participants)
                .joinedload(StageEventParticipant.member)
                .joinedload(Member.user)
            )
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

    async def get_hiring_team(
        self,
        organization_id: str,
        team_id: str,
    ) -> HiringTeam | None:
        result = await self.db.execute(
            select(HiringTeam)
            .options(
                joinedload(HiringTeam.members).joinedload(HiringTeamMember.member).joinedload(Member.user)
            )
            .where(
                HiringTeam.organizationId == organization_id,
                HiringTeam.id == team_id,
                HiringTeam.isActive.is_(True),
            )
        )
        return result.unique().scalar_one_or_none()

    async def count_interviews_for_member_on_date(
        self,
        organization_id: str,
        member_id: str,
        target_date: date,
    ) -> int:
        result = await self.db.execute(
            select(func.count(StageEvent.id))
            .join(StageEventParticipant, StageEventParticipant.eventId == StageEvent.id)
            .where(
                StageEvent.organizationId == organization_id,
                StageEventParticipant.memberId == member_id,
                StageEventParticipant.role == "INTERVIEWER",
                func.date(StageEvent.scheduledStartAt) == target_date,
            )
        )
        return int(result.scalar_one())

    async def get_stage_event_with_participants(
        self,
        organization_id: str,
        event_id: str,
    ) -> StageEvent | None:
        result = await self.db.execute(
            select(StageEvent)
            .options(
                joinedload(StageEvent.application).joinedload(CandidateApplication.candidate),
                joinedload(StageEvent.application).joinedload(CandidateApplication.jobPosting),
                joinedload(StageEvent.stage),
                selectinload(StageEvent.participants).joinedload(StageEventParticipant.member).joinedload(Member.user),
            )
            .where(
                StageEvent.organizationId == organization_id,
                StageEvent.id == event_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_my_interviews(
        self,
        organization_id: str,
        member_id: str,
    ) -> list[StageEventParticipant]:
        result = await self.db.execute(
            select(StageEventParticipant)
            .options(
                joinedload(StageEventParticipant.event)
                .joinedload(StageEvent.application)
                .joinedload(CandidateApplication.candidate),
                joinedload(StageEventParticipant.event)
                .joinedload(StageEvent.application)
                .joinedload(CandidateApplication.jobPosting),
                joinedload(StageEventParticipant.event)
                .joinedload(StageEvent.stage),
                joinedload(StageEventParticipant.member).joinedload(Member.user),
            )
            .where(
                StageEventParticipant.memberId == member_id,
                StageEventParticipant.event.has(StageEvent.organizationId == organization_id),
            )
            .order_by(StageEventParticipant.createdAt.desc())
        )
        return list(result.unique().scalars().all())
