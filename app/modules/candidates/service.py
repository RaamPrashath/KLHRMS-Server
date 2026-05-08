from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruitment import (
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    JobPosting,
    PipelineStage,
)
from app.modules.candidates.repository import CandidatePipelineRepository
from app.modules.candidates.schema import (
    CandidateApplicationDetailRead,
    CandidateSummaryRead,
    MoveApplicationStageRequest,
    PipelineApplicationRead,
    PipelineBoardRead,
    PipelineJobPostingRead,
    PipelineStageCreateRequest,
    PipelineStageHistoryRead,
    PipelineStageRead,
    PipelineStageUpdateRequest,
)


DEFAULT_PIPELINE_STAGES: list[dict[str, object]] = [
    {"name": "Applied", "order": 1, "color": "#6366f1", "isDefault": True, "isFinal": False},
    {"name": "Screening", "order": 2, "color": "#f59e0b", "isDefault": True, "isFinal": False},
    {"name": "Interview Round 1", "order": 3, "color": "#3b82f6", "isDefault": True, "isFinal": False},
    {"name": "Interview Round 2", "order": 4, "color": "#8b5cf6", "isDefault": False, "isFinal": False},
    {"name": "Offer", "order": 5, "color": "#10b981", "isDefault": True, "isFinal": False},
    {"name": "Hired", "order": 6, "color": "#22c55e", "isDefault": True, "isFinal": True},
    {"name": "Onboarded", "order": 7, "color": "#06b6d4", "isDefault": True, "isFinal": True},
    {"name": "Rejected", "order": 8, "color": "#ef4444", "isDefault": True, "isFinal": True},
]


def _is_protected_stage(stage: PipelineStage) -> bool:
    return stage.name.strip().lower() == "applied" and stage.order == 1


def _serialize_candidate(candidate: Candidate) -> CandidateSummaryRead:
    return CandidateSummaryRead(
        id=candidate.id,
        firstName=candidate.firstName,
        lastName=candidate.lastName,
        email=candidate.email,
        phone=candidate.phone,
        linkedinUrl=candidate.linkedinUrl,
        resumeUrl=candidate.resumeUrl,
    )


def _serialize_application(
    application: CandidateApplication,
    stage: PipelineStage,
) -> PipelineApplicationRead:
    return PipelineApplicationRead(
        id=application.id,
        jobPostingId=application.jobPostingId,
        pipelineStageId=application.pipelineStageId,
        currentStage=stage.name,
        candidate=_serialize_candidate(application.candidate),
        score=application.score,
        source=application.source,
        appliedDate=application.appliedAt,
        resumeUrl=application.candidate.resumeUrl,
    )


def _serialize_stage(stage: PipelineStage) -> PipelineStageRead:
    applications = sorted(
        stage.applications or [],
        key=lambda application: application.appliedAt,
        reverse=True,
    )
    return PipelineStageRead(
        id=stage.id,
        jobPostingId=stage.jobPostingId,
        name=stage.name,
        order=stage.order,
        color=stage.color,
        isDefault=stage.isDefault,
        isFinal=stage.isFinal,
        isProtected=_is_protected_stage(stage),
        applications=[
            _serialize_application(application, stage) for application in applications
        ],
    )


def _serialize_history(history: ApplicationStageHistory) -> PipelineStageHistoryRead:
    moved_by_name = None
    if history.movedBy is not None and history.movedBy.user is not None:
        moved_by_name = history.movedBy.user.name or history.movedBy.user.email

    return PipelineStageHistoryRead(
        id=history.id,
        fromStageId=history.fromStageId,
        fromStageName=history.fromStage.name if history.fromStage is not None else None,
        toStageId=history.toStageId,
        toStageName=history.toStage.name if history.toStage is not None else None,
        movedByMemberId=history.movedByMemberId,
        movedByName=moved_by_name,
        note=history.note,
        createdAt=history.createdAt,
    )


def _serialize_detail(application: CandidateApplication) -> CandidateApplicationDetailRead:
    histories = sorted(
        application.stageHistory or [],
        key=lambda history: history.createdAt,
        reverse=True,
    )
    return CandidateApplicationDetailRead(
        id=application.id,
        jobPostingId=application.jobPostingId,
        jobPostingTitle=application.jobPosting.title,
        pipelineStageId=application.pipelineStageId,
        currentStage=application.pipelineStage.name,
        candidate=_serialize_candidate(application.candidate),
        source=application.source,
        score=application.score,
        notes=application.notes,
        resumeUrl=application.candidate.resumeUrl,
        appliedAt=application.appliedAt,
        lastActivityAt=application.lastActivityAt,
        stageHistory=[_serialize_history(history) for history in histories],
    )


async def _ensure_default_stages(
    db: AsyncSession,
    repository: CandidatePipelineRepository,
    organization_id: str,
    job_posting_id: str,
) -> list[PipelineStage]:
    stages = await repository.list_stages_for_job(organization_id, job_posting_id)
    if stages:
        return stages

    new_stages = [
        PipelineStage(
            organizationId=organization_id,
            jobPostingId=job_posting_id,
            name=str(stage["name"]),
            order=int(stage["order"]),
            color=str(stage["color"]),
            isDefault=bool(stage["isDefault"]),
            isFinal=bool(stage["isFinal"]),
        )
        for stage in DEFAULT_PIPELINE_STAGES
    ]
    db.add_all(new_stages)
    await db.commit()
    return await repository.list_stages_for_job(organization_id, job_posting_id)


async def _normalize_stage_order(db: AsyncSession, stages: list[PipelineStage]) -> None:
    for index, stage in enumerate(stages, start=1):
        stage.order = -(index + 1000)
        db.add(stage)
    await db.flush()
    for index, stage in enumerate(stages, start=1):
        stage.order = index
        db.add(stage)
    await db.flush()


async def list_job_postings(
    db: AsyncSession,
    organization_id: str,
) -> list[PipelineJobPostingRead]:
    repository = CandidatePipelineRepository(db)
    postings = await repository.list_job_postings(organization_id)
    return [
        PipelineJobPostingRead(id=posting.id, title=posting.title, status=posting.status.value)
        for posting in postings
    ]


async def get_pipeline_board(
    db: AsyncSession,
    organization_id: str,
    job_posting_id: str,
) -> PipelineBoardRead:
    repository = CandidatePipelineRepository(db)
    posting = await repository.get_job_posting(organization_id, job_posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    stages = await _ensure_default_stages(db, repository, organization_id, job_posting_id)
    return PipelineBoardRead(
        jobPostingId=job_posting_id,
        stages=[_serialize_stage(stage) for stage in stages],
    )


async def move_application_stage(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    application_id: str,
    body: MoveApplicationStageRequest,
) -> PipelineApplicationRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    target_stage = await repository.get_stage(organization_id, body.toStageId)
    if target_stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if target_stage.jobPostingId != application.jobPostingId:
        raise HTTPException(status_code=400, detail="Target stage does not belong to this job posting")

    from_stage_id = application.pipelineStageId
    application.pipelineStageId = target_stage.id
    history = ApplicationStageHistory(
        organizationId=organization_id,
        applicationId=application.id,
        fromStageId=from_stage_id,
        toStageId=target_stage.id,
        movedByMemberId=actor_member_id,
        note=body.note,
    )
    db.add(application)
    await repository.add_history(history)
    await db.commit()

    refreshed = await repository.get_application(organization_id, application_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_application(refreshed, target_stage)


async def create_stage(
    db: AsyncSession,
    organization_id: str,
    body: PipelineStageCreateRequest,
) -> PipelineStageRead:
    repository = CandidatePipelineRepository(db)
    posting = await repository.get_job_posting(organization_id, body.jobPostingId)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    stages = await _ensure_default_stages(db, repository, organization_id, body.jobPostingId)
    insert_index = len(stages)
    if body.afterStageId is not None:
        after_stage = next((stage for stage in stages if stage.id == body.afterStageId), None)
        if after_stage is None:
            raise HTTPException(status_code=404, detail="Anchor stage not found")
        insert_index = sorted(stages, key=lambda stage: stage.order).index(after_stage) + 1

    new_stage = PipelineStage(
        organizationId=organization_id,
        jobPostingId=body.jobPostingId,
        name=body.name.strip(),
        order=10_000,
        color=None,
        isDefault=False,
        isFinal=False,
    )
    await repository.add_stage(new_stage)
    ordered = sorted(stages, key=lambda stage: stage.order)
    ordered.insert(insert_index, new_stage)
    await _normalize_stage_order(db, ordered)
    await db.commit()
    stages = await repository.list_stages_for_job(organization_id, body.jobPostingId)
    created = next(stage for stage in stages if stage.id == new_stage.id)
    return _serialize_stage(created)


async def update_stage(
    db: AsyncSession,
    organization_id: str,
    stage_id: str,
    body: PipelineStageUpdateRequest,
) -> PipelineStageRead:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")

    if body.name is not None:
        stage.name = body.name.strip()
    if body.order is not None:
        stages = await repository.list_stages_for_job(organization_id, stage.jobPostingId)
        ordered = [item for item in sorted(stages, key=lambda item: item.order) if item.id != stage.id]
        target_index = min(max(body.order, 1), len(ordered) + 1) - 1
        ordered.insert(target_index, stage)
        await _normalize_stage_order(db, ordered)

    db.add(stage)
    await db.commit()
    stages = await repository.list_stages_for_job(organization_id, stage.jobPostingId)
    updated = next(item for item in stages if item.id == stage.id)
    return _serialize_stage(updated)


async def delete_stage(
    db: AsyncSession,
    organization_id: str,
    stage_id: str,
) -> None:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if _is_protected_stage(stage):
        raise HTTPException(status_code=400, detail="Applied stage cannot be deleted")
    application_count = await repository.count_stage_applications(organization_id, stage_id)
    if application_count > 0:
        raise HTTPException(status_code=400, detail="Move candidates out of this stage before deleting it")
    history_count = await repository.count_stage_history(organization_id, stage_id)
    if history_count > 0:
        raise HTTPException(status_code=400, detail="Stages with movement history cannot be deleted")

    job_posting_id = stage.jobPostingId
    await db.delete(stage)
    await db.flush()
    stages = await repository.list_stages_for_job(organization_id, job_posting_id)
    await _normalize_stage_order(db, sorted(stages, key=lambda item: item.order))
    await db.commit()


async def get_application_detail(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
) -> CandidateApplicationDetailRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application_detail(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_detail(application)
