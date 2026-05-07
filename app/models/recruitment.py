from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base, generate_uuid

import enum


# =========================================================
# ENUMS
# =========================================================

class JobPostingStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class ApplicationSource(str, enum.Enum):
    LINKEDIN = "LINKEDIN"
    REFERRAL = "REFERRAL"
    COMPANY_WEBSITE = "COMPANY_WEBSITE"
    JOB_BOARD = "JOB_BOARD"
    DIRECT = "DIRECT"
    OTHER = "OTHER"


# =========================================================
# CANDIDATE
# =========================================================

class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    userId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    firstName: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    lastName: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(String)

    linkedinUrl: Mapped[str | None] = mapped_column(String)

    resumeUrl: Mapped[str | None] = mapped_column(Text)

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updatedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # RELATIONSHIPS

    organization = relationship(
        "Organization",
        back_populates="candidates",
    )

    user = relationship(
        "User",
        back_populates="candidateProfiles",
    )

    applications = relationship(
        "CandidateApplication",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organizationId",
            "email",
            name="uq_candidate_org_email",
        ),
    )


# =========================================================
# JOB POSTING
# =========================================================

class JobPosting(Base):
    __tablename__ = "job_posting"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    requirements: Mapped[str | None] = mapped_column(Text)

    status: Mapped[JobPostingStatus] = mapped_column(
        Enum(JobPostingStatus),
        nullable=False,
        default=JobPostingStatus.DRAFT,
        index=True,
    )

    publishedAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True)
    )

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updatedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # RELATIONSHIPS

    organization = relationship(
        "Organization",
        back_populates="jobPostings",
    )

    applications = relationship(
        "CandidateApplication",
        back_populates="jobPosting",
        cascade="all, delete-orphan",
    )

    pipelineStages = relationship(
        "PipelineStage",
        back_populates="jobPosting",
        cascade="all, delete-orphan",
    )


# =========================================================
# PIPELINE STAGE
# =========================================================

class PipelineStage(Base):
    __tablename__ = "pipeline_stage"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    jobPostingId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_posting.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    color: Mapped[str | None] = mapped_column(String)

    isDefault: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    isFinal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updatedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # RELATIONSHIPS

    organization = relationship(
        "Organization",
        back_populates="pipelineStages",
    )

    jobPosting = relationship(
        "JobPosting",
        back_populates="pipelineStages",
    )

    applications = relationship(
        "CandidateApplication",
        back_populates="pipelineStage",
    )

    fromStageHistories = relationship(
        "ApplicationStageHistory",
        foreign_keys="ApplicationStageHistory.fromStageId",
        back_populates="fromStage",
    )

    toStageHistories = relationship(
        "ApplicationStageHistory",
        foreign_keys="ApplicationStageHistory.toStageId",
        back_populates="toStage",
    )

    __table_args__ = (
        UniqueConstraint(
            "jobPostingId",
            "order",
            name="uq_pipeline_stage_order",
        ),
    )


# =========================================================
# CANDIDATE APPLICATION
# =========================================================

class CandidateApplication(Base):
    __tablename__ = "candidate_application"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    candidateId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate.id", ondelete="CASCADE"),
        nullable=False,
    )

    jobPostingId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_posting.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pipelineStageId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    source: Mapped[ApplicationSource] = mapped_column(
        Enum(ApplicationSource),
        nullable=False,
        default=ApplicationSource.DIRECT,
    )

    score: Mapped[int | None] = mapped_column(Integer)

    notes: Mapped[str | None] = mapped_column(Text)

    appliedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    lastActivityAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # RELATIONSHIPS

    organization = relationship(
        "Organization",
        back_populates="candidateApplications",
    )

    candidate = relationship(
        "Candidate",
        back_populates="applications",
    )

    jobPosting = relationship(
        "JobPosting",
        back_populates="applications",
    )

    pipelineStage = relationship(
        "PipelineStage",
        back_populates="applications",
    )

    stageHistory = relationship(
        "ApplicationStageHistory",
        back_populates="application",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "candidateId",
            "jobPostingId",
            name="uq_candidate_job_application",
        ),
        Index(
            "ix_candidate_application_org_stage",
            "organizationId",
            "pipelineStageId",
        ),
    )


# =========================================================
# APPLICATION STAGE HISTORY
# =========================================================

class ApplicationStageHistory(Base):
    __tablename__ = "application_stage_history"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    applicationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_application.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    fromStageId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    toStageId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    movedByMemberId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    note: Mapped[str | None] = mapped_column(Text)

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # RELATIONSHIPS

    organization = relationship(
        "Organization",
        back_populates="applicationStageHistories",
    )

    application = relationship(
        "CandidateApplication",
        back_populates="stageHistory",
    )

    fromStage = relationship(
        "PipelineStage",
        foreign_keys=[fromStageId],
        back_populates="fromStageHistories",
    )

    toStage = relationship(
        "PipelineStage",
        foreign_keys=[toStageId],
        back_populates="toStageHistories",
    )

    movedBy = relationship(
        "Member",
        back_populates="movedApplicationHistories",
    )