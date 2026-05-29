from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.recruitment import (
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    JobPosting,
    JobRequisition,
    OfferDispatchBatch,
    OfferDispatchBatchStatus,
    OfferLetter,
    OfferStatus,
    OfferTemplate,
    OfferTemplateCategory,
    OfferTemplateSection,
    PipelineStage,
    StageType,
)


class OfferRepository:
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

    async def get_offer_stage_for_job(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> PipelineStage | None:
        result = await self.db.execute(
            select(PipelineStage)
            .where(
                PipelineStage.organizationId == organization_id,
                PipelineStage.jobPostingId == job_posting_id,
                PipelineStage.stageType == StageType.OFFER,
            )
            .order_by(PipelineStage.order.asc())
        )
        return result.scalars().first()

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

    async def list_latest_offers_for_applications(
        self,
        organization_id: str,
        application_ids: list[str],
    ) -> dict[str, OfferLetter]:
        if not application_ids:
            return {}
        result = await self.db.execute(
            select(OfferLetter)
            .where(
                OfferLetter.organizationId == organization_id,
                OfferLetter.applicationId.in_(application_ids),
            )
            .order_by(OfferLetter.createdAt.desc(), OfferLetter.sentAt.desc().nullslast())
        )
        latest: dict[str, OfferLetter] = {}
        for offer in result.scalars().all():
            latest.setdefault(offer.applicationId, offer)
        return latest

    async def get_latest_batch_for_stage(
        self,
        organization_id: str,
        job_posting_id: str,
        stage_id: str,
    ) -> OfferDispatchBatch | None:
        result = await self.db.execute(
            select(OfferDispatchBatch)
            .where(
                OfferDispatchBatch.organizationId == organization_id,
                OfferDispatchBatch.jobPostingId == job_posting_id,
                OfferDispatchBatch.stageId == stage_id,
            )
            .order_by(OfferDispatchBatch.createdAt.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_batch_detail(
        self,
        organization_id: str,
        batch_id: str,
    ) -> OfferDispatchBatch | None:
        result = await self.db.execute(
            select(OfferDispatchBatch)
            .options(
                joinedload(OfferDispatchBatch.organization),
                joinedload(OfferDispatchBatch.jobPosting).joinedload(JobPosting.requisition),
                selectinload(OfferDispatchBatch.offerLetters)
                .joinedload(OfferLetter.application)
                .joinedload(CandidateApplication.candidate),
            )
            .where(
                OfferDispatchBatch.organizationId == organization_id,
                OfferDispatchBatch.id == batch_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_offer_letters_for_batch(
        self,
        organization_id: str,
        batch_id: str,
    ) -> list[OfferLetter]:
        result = await self.db.execute(
            select(OfferLetter)
            .where(
                OfferLetter.organizationId == organization_id,
                OfferLetter.batchId == batch_id,
            )
            .order_by(OfferLetter.createdAt.asc())
        )
        return list(result.scalars().all())

    async def list_offer_letters_for_application(
        self,
        organization_id: str,
        application_id: str,
    ) -> list[OfferLetter]:
        result = await self.db.execute(
            select(OfferLetter)
            .where(
                OfferLetter.organizationId == organization_id,
                OfferLetter.applicationId == application_id,
            )
            .order_by(OfferLetter.createdAt.desc(), OfferLetter.sentAt.desc().nullslast())
        )
        return list(result.scalars().all())

    async def get_offer_by_token(self, token: str) -> OfferLetter | None:
        result = await self.db.execute(
            select(OfferLetter)
            .options(
                joinedload(OfferLetter.application).joinedload(CandidateApplication.jobPosting),
            )
            .where(OfferLetter.candidateToken == token)
        )
        return result.unique().scalar_one_or_none()

    async def get_latest_offer_for_application(
        self,
        organization_id: str,
        application_id: str,
    ) -> OfferLetter | None:
        result = await self.db.execute(
            select(OfferLetter)
            .where(
                OfferLetter.organizationId == organization_id,
                OfferLetter.applicationId == application_id,
            )
            .order_by(OfferLetter.createdAt.desc(), OfferLetter.sentAt.desc().nullslast())
            .limit(1)
        )
        return result.scalar_one_or_none()

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

    async def add_stage_history(self, history: ApplicationStageHistory) -> ApplicationStageHistory:
        self.db.add(history)
        await self.db.flush()
        return history

    async def reset_failed_offers_for_batch(
        self,
        organization_id: str,
        batch_id: str,
    ) -> int:
        offers = await self.list_offer_letters_for_batch(organization_id, batch_id)
        reset_count = 0
        for offer in offers:
            if offer.status == OfferStatus.FAILED or offer.emailError:
                offer.status = OfferStatus.DRAFT
                offer.emailError = None
                self.db.add(offer)
                reset_count += 1
        await self.db.flush()
        return reset_count

    async def list_templates(
        self,
        organization_id: str,
        *,
        search: str | None = None,
        status: str | None = None,
    ) -> list[OfferTemplate]:
        query = (
            select(OfferTemplate)
            .options(selectinload(OfferTemplate.categories))
            .where(OfferTemplate.organizationId == organization_id)
        )
        if status:
            query = query.where(OfferTemplate.status == status)
        else:
            query = query.where(OfferTemplate.status.in_(["DRAFT", "ACTIVE"]))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(func.lower(OfferTemplate.name).like(func.lower(pattern)))
        query = query.order_by(
            OfferTemplate.lastUsedAt.desc().nullslast(),
            OfferTemplate.updatedAt.desc(),
        )
        result = await self.db.execute(query)
        return list(result.unique().scalars().all())

    async def get_recent_template(self, organization_id: str) -> OfferTemplate | None:
        templates = await self.list_templates(organization_id)
        return templates[0] if templates else None

    async def get_template_detail(
        self,
        organization_id: str,
        template_id: str,
    ) -> OfferTemplate | None:
        result = await self.db.execute(
            select(OfferTemplate)
            .options(
                selectinload(OfferTemplate.categories),
                selectinload(OfferTemplate.sections),
            )
            .where(
                OfferTemplate.organizationId == organization_id,
                OfferTemplate.id == template_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_category(
        self,
        organization_id: str,
        template_id: str,
        category_id: str,
    ) -> OfferTemplateCategory | None:
        result = await self.db.execute(
            select(OfferTemplateCategory).where(
                OfferTemplateCategory.organizationId == organization_id,
                OfferTemplateCategory.templateId == template_id,
                OfferTemplateCategory.id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_section(
        self,
        organization_id: str,
        template_id: str,
        category_id: str,
        section_key: str,
    ) -> OfferTemplateSection | None:
        result = await self.db.execute(
            select(OfferTemplateSection).where(
                OfferTemplateSection.organizationId == organization_id,
                OfferTemplateSection.templateId == template_id,
                OfferTemplateSection.categoryId == category_id,
                OfferTemplateSection.sectionKey == section_key,
            )
        )
        return result.scalar_one_or_none()

    async def template_has_in_progress_batch(
        self,
        organization_id: str,
        template_id: str,
    ) -> bool:
        result = await self.db.execute(
            select(OfferDispatchBatch.id)
            .where(
                OfferDispatchBatch.organizationId == organization_id,
                OfferDispatchBatch.templateId == template_id,
                OfferDispatchBatch.status.in_(
                    [
                        OfferDispatchBatchStatus.QUEUED,
                        OfferDispatchBatchStatus.PROCESSING,
                    ]
                ),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_template_names(self, organization_id: str) -> set[str]:
        result = await self.db.execute(
            select(OfferTemplate.name).where(OfferTemplate.organizationId == organization_id)
        )
        return {str(name) for name in result.scalars().all()}

    async def add(self, item: object) -> None:
        self.db.add(item)
        await self.db.flush()

    async def add_all(self, items: list[object]) -> None:
        self.db.add_all(items)
        await self.db.flush()

    async def delete(self, item: object) -> None:
        await self.db.delete(item)
        await self.db.flush()

    async def withdraw_sent_offers_for_applications(
        self,
        organization_id: str,
        application_ids: list[str],
    ) -> None:
        if not application_ids:
            return
        result = await self.db.execute(
            select(OfferLetter).where(
                OfferLetter.organizationId == organization_id,
                OfferLetter.applicationId.in_(application_ids),
                OfferLetter.status == OfferStatus.SENT,
            )
        )
        for offer in result.scalars().all():
            # A resend creates a new token/PDF later; older sent offers must not stay actionable.
            offer.status = OfferStatus.WITHDRAWN
            self.db.add(offer)
        await self.db.flush()
