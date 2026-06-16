from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.recruitment import (
    CandidateApplication,
    DocumentCollectionField,
    DocumentCollectionRequest,
    DocumentCollectionRequestStatus,
    DocumentCollectionTemplate,
    JobPosting,
    PipelineStage,
)


class DocumentCollectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_templates(
        self,
        organization_id: str,
        *,
        search: str | None = None,
        status: str | None = None,
    ) -> list[DocumentCollectionTemplate]:
        query = (
            select(DocumentCollectionTemplate)
            .options(selectinload(DocumentCollectionTemplate.fields))
            .where(DocumentCollectionTemplate.organizationId == organization_id)
        )
        if status:
            query = query.where(DocumentCollectionTemplate.status == status)
        else:
            query = query.where(DocumentCollectionTemplate.status.in_(["DRAFT", "ACTIVE"]))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(func.lower(DocumentCollectionTemplate.name).like(func.lower(pattern)))
        query = query.order_by(
            DocumentCollectionTemplate.lastUsedAt.desc().nullslast(),
            DocumentCollectionTemplate.updatedAt.desc(),
        )
        result = await self.db.execute(query)
        return list(result.unique().scalars().all())

    async def get_template_detail(
        self,
        organization_id: str,
        template_id: str,
    ) -> DocumentCollectionTemplate | None:
        result = await self.db.execute(
            select(DocumentCollectionTemplate)
            .options(selectinload(DocumentCollectionTemplate.fields))
            .where(
                DocumentCollectionTemplate.organizationId == organization_id,
                DocumentCollectionTemplate.id == template_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_template_names(self, organization_id: str) -> set[str]:
        result = await self.db.execute(
            select(DocumentCollectionTemplate.name).where(DocumentCollectionTemplate.organizationId == organization_id)
        )
        return {str(name) for name in result.scalars().all()}

    async def get_job_by_slug(self, organization_id: str, job_slug: str) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting)
            .options(joinedload(JobPosting.organization))
            .where(
                JobPosting.organizationId == organization_id,
                JobPosting.slug == job_slug,
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
            select(PipelineStage).where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.slug == stage_slug,
            )
        )
        return result.scalar_one_or_none()

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

    async def list_latest_requests_for_applications(
        self,
        organization_id: str,
        application_ids: list[str],
    ) -> dict[str, DocumentCollectionRequest]:
        if not application_ids:
            return {}
        result = await self.db.execute(
            select(DocumentCollectionRequest)
            .where(
                DocumentCollectionRequest.organizationId == organization_id,
                DocumentCollectionRequest.applicationId.in_(application_ids),
            )
            .order_by(DocumentCollectionRequest.createdAt.desc())
        )
        latest: dict[str, DocumentCollectionRequest] = {}
        for request in result.scalars().all():
            if request.applicationId not in latest:
                latest[request.applicationId] = request
        return latest

    async def get_request_by_token(self, token: str) -> DocumentCollectionRequest | None:
        result = await self.db.execute(
            select(DocumentCollectionRequest)
            .options(
                joinedload(DocumentCollectionRequest.application)
                .joinedload(CandidateApplication.candidate),
                joinedload(DocumentCollectionRequest.application)
                .joinedload(CandidateApplication.jobPosting)
                .joinedload(JobPosting.organization),
            )
            .where(DocumentCollectionRequest.candidateToken == token)
        )
        return result.unique().scalar_one_or_none()

    async def get_request_detail(
        self,
        organization_id: str,
        request_id: str,
    ) -> DocumentCollectionRequest | None:
        result = await self.db.execute(
            select(DocumentCollectionRequest).where(
                DocumentCollectionRequest.organizationId == organization_id,
                DocumentCollectionRequest.id == request_id,
            )
        )
        return result.scalar_one_or_none()

    async def template_has_pending_requests(self, organization_id: str, template_id: str) -> bool:
        result = await self.db.execute(
            select(DocumentCollectionRequest.id)
            .where(
                DocumentCollectionRequest.organizationId == organization_id,
                DocumentCollectionRequest.templateId == template_id,
                DocumentCollectionRequest.status == DocumentCollectionRequestStatus.PENDING,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def add(self, item: object) -> None:
        self.db.add(item)
        await self.db.flush()

    async def add_all(self, items: list[object]) -> None:
        self.db.add_all(items)
        await self.db.flush()

    async def delete(self, item: object) -> None:
        await self.db.delete(item)
        await self.db.flush()

    async def delete_fields_for_template(self, organization_id: str, template_id: str) -> None:
        from sqlalchemy import delete as sa_delete
        await self.db.execute(
            sa_delete(DocumentCollectionField).where(
                DocumentCollectionField.organizationId == organization_id,
                DocumentCollectionField.templateId == template_id,
            )
        )
        await self.db.flush()
