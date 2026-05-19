import enum

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid

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


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"


class JobRequisitionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    ACTIVE_HIRING = "ACTIVE_HIRING"
    FILLED = "FILLED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class HiringReason(str, enum.Enum):
    NEW_ROLE = "NEW_ROLE"
    REPLACEMENT = "REPLACEMENT"
    TEAM_EXPANSION = "TEAM_EXPANSION"
    URGENT_REQUIREMENT = "URGENT_REQUIREMENT"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    CLIENT_REQUIREMENT = "CLIENT_REQUIREMENT"


class RequisitionPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SalaryVisibility(str, enum.Enum):
    INTERNAL_ONLY = "INTERNAL_ONLY"
    PUBLIC = "PUBLIC"


class ExperienceLevel(str, enum.Enum):
    ENTRY = "ENTRY"
    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    STAFF = "STAFF"
    PRINCIPAL = "PRINCIPAL"
    LEAD = "LEAD"
    HEAD = "HEAD"
    EXECUTIVE = "EXECUTIVE"

class RequisitionApprovalDecision(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class StageType(str, enum.Enum):
    DEFAULT = "DEFAULT"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    HIRED = "HIRED"
    REJECTED = "REJECTED"


class InterviewType(str, enum.Enum):
    SCREENING = "SCREENING"
    TECHNICAL = "TECHNICAL"
    CULTURAL = "CULTURAL"
    MANAGERIAL = "MANAGERIAL"
    HR = "HR"
    FINAL = "FINAL"
    OTHER = "OTHER"


class EventStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class InterviewOutcome(str, enum.Enum):
    PENDING = "PENDING"
    STRONG_YES = "STRONG_YES"
    YES = "YES"
    NEUTRAL = "NEUTRAL"
    NO = "NO"
    STRONG_NO = "STRONG_NO"


class OfferStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"

# =========================================================
# JOB REQUISITION
# =========================================================


class JobRequisition(Base):
    __tablename__ = "job_requisition"

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

    departmentId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    employmentType: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType),
        nullable=False,
        default=EmploymentType.FULL_TIME,
    )

    openings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    salaryMin: Mapped[float | None] = mapped_column(Float)

    salaryMax: Mapped[float | None] = mapped_column(Float)

    currency: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="INR",
    )

    description: Mapped[str | None] = mapped_column(Text)

    requirements: Mapped[str | None] = mapped_column(Text)

    skills: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
    )

    location: Mapped[str | None] = mapped_column(String)

    isRemote: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    raisedById: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    targetDate: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    # HIRING CONTEXT
    hiringReason: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[str] = mapped_column(String, nullable=False, default="MEDIUM")
    replacementForId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    businessJustification: Mapped[str | None] = mapped_column(Text, nullable=True)

    # COMPENSATION
    salaryVisibility: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="INTERNAL_ONLY",
    )

    # CANDIDATE REQUIREMENTS
    experienceLevel: Mapped[str | None] = mapped_column(String, nullable=True)
    minExperience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    education: Mapped[str | None] = mapped_column(String, nullable=True)
    certifications: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        default=list,
    )

    # POSTING CONTENT (Tiptap HTML)
    roleSummary: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirementsRich: Mapped[str | None] = mapped_column(Text, nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
    aboutTeam: Mapped[str | None] = mapped_column(Text, nullable=True)

    # REQUISITION NUMBER
    requisitionNumber: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[JobRequisitionStatus] = mapped_column(
        Enum(JobRequisitionStatus),
        nullable=False,
        default=JobRequisitionStatus.DRAFT,
        index=True,
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

    closedAt: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    organization = relationship(
        "Organization",
        back_populates="jobRequisitions",
    )

    department = relationship("Department")

    raisedBy = relationship(
        "Member",
        foreign_keys=[raisedById],
        back_populates="raisedJobRequisitions",
    )

    replacementFor = relationship(
        "Member",
        foreign_keys=[replacementForId],
        uselist=False,
    )

    approvals = relationship(
        "RequisitionApproval",
        back_populates="requisition",
        cascade="all, delete-orphan",
    )

    activityLogs = relationship(
        "RequisitionActivityLog",
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="RequisitionActivityLog.createdAt.desc()",
    )

    __table_args__ = (
        Index("ix_job_requisition_org_status", "organizationId", "status"),
        Index("ix_job_requisition_org_raised_by", "organizationId", "raisedById"),
        Index("ix_job_requisition_org_replacement", "organizationId", "replacementForId"),
    )


# =========================================================
# REQUISITION APPROVAL
# =========================================================


class RequisitionApproval(Base):
    __tablename__ = "requisition_approval"

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

    requisitionId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_requisition.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    approverId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    decision: Mapped[RequisitionApprovalDecision] = mapped_column(
        Enum(RequisitionApprovalDecision),
        nullable=False,
        default=RequisitionApprovalDecision.PENDING,
        index=True,
    )

    comment: Mapped[str | None] = mapped_column(Text)

    decidedAt: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    organization = relationship(
        "Organization",
        back_populates="requisitionApprovals",
    )

    requisition = relationship(
        "JobRequisition",
        back_populates="approvals",
    )

    approver = relationship(
        "Member",
        foreign_keys=[approverId],
        back_populates="requisitionApprovals",
    )

    __table_args__ = (
        UniqueConstraint(
            "requisitionId",
            "approverId",
            name="uq_requisition_approval_requisition_approver",
        ),
    )


class RequisitionActivityLog(Base):
    __tablename__ = "requisition_activity_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    requisitionId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_requisition.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actorId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # action values: "CREATED", "SUBMITTED", "APPROVED", "REJECTED",
    #                "EDITED", "CLOSED", "REOPENED", "PUBLISHED", "ARCHIVED"
    fieldChanges: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="requisitionActivityLogs",
    )
    requisition = relationship(
        "JobRequisition",
        back_populates="activityLogs",
    )
    actor = relationship(
        "Member",
        foreign_keys=[actorId],
    )

    __table_args__ = (
        Index("ix_requisition_activity_log_org_action", "organizationId", "action"),
    )


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

    portfolioUrl: Mapped[str | None] = mapped_column(String)

    currentCompany: Mapped[str | None] = mapped_column(String)

    currentTitle: Mapped[str | None] = mapped_column(String)

    totalExperience: Mapped[str | None] = mapped_column(String)

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

    requisitionId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("job_requisition.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(160),
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

    requisition = relationship("JobRequisition", foreign_keys=[requisitionId])

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

    hiringTeams = relationship(
        "HiringTeam",
        back_populates="jobPosting",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organizationId",
            "slug",
            name="uq_job_posting_org_slug",
        ),
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

    stageId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    order: Mapped[float] = mapped_column(
        Float,
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

    stageType: Mapped[StageType] = mapped_column(
        Enum(StageType),
        nullable=False,
        default=StageType.DEFAULT,
    )

    meetingEnabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    offerLetterEnabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    evaluationEnabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    evaluationType: Mapped[str | None] = mapped_column(String(32))

    evaluationIncludeTotal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    evaluationIncludeAnalysis: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    dueDate: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    extendToNextWorkingDay: Mapped[bool] = mapped_column(
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

    stageEvents = relationship(
        "StageEvent",
        back_populates="stage",
        cascade="all, delete-orphan",
    )

    evaluationWorkspace = relationship(
        "StageEvaluationWorkspace",
        back_populates="stage",
        cascade="all, delete-orphan",
        uselist=False,
    )

    evaluationCategories = relationship(
        "StageEvaluationCategory",
        back_populates="stage",
        cascade="all, delete-orphan",
        order_by="StageEvaluationCategory.order",
    )

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
        UniqueConstraint(
            "jobPostingId",
            "slug",
            name="uq_pipeline_stage_job_slug",
        ),
    )


# =========================================================
# STAGE EVALUATION WORKSPACE
# =========================================================

class StageEvaluationWorkspace(Base):
    __tablename__ = "stage_evaluation_workspace"

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

    stageId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    googleSpreadsheetId: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    googleSpreadsheetUrl: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    googleSheetId: Mapped[int | None] = mapped_column(Integer)

    googleSheetTitle: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    createdByMemberId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    organization = relationship(
        "Organization",
        back_populates="stageEvaluationWorkspaces",
    )

    stage = relationship(
        "PipelineStage",
        back_populates="evaluationWorkspace",
    )

    createdBy = relationship(
        "Member",
        foreign_keys=[createdByMemberId],
        back_populates="createdEvaluationWorkspaces",
    )

    __table_args__ = (
        UniqueConstraint(
            "stageId",
            name="uq_stage_evaluation_workspace_stage",
        ),
        UniqueConstraint(
            "organizationId",
            "stageId",
            name="uq_stage_evaluation_workspace_org_stage",
        ),
        Index("ix_stage_evaluation_workspace_org_stage", "organizationId", "stageId"),
    )


# =========================================================
# STAGE EVALUATION CATEGORY
# =========================================================

class StageEvaluationCategory(Base):
    __tablename__ = "stage_evaluation_category"

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

    stageId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    valueType: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="NUMERIC",
    )

    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
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

    organization = relationship(
        "Organization",
        back_populates="stageEvaluationCategories",
    )

    stage = relationship(
        "PipelineStage",
        back_populates="evaluationCategories",
    )

    __table_args__ = (
        UniqueConstraint(
            "stageId",
            "order",
            name="uq_stage_evaluation_category_order",
        ),
        Index("ix_stage_evaluation_category_org_stage", "organizationId", "stageId"),
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

    internalNotes: Mapped[str | None] = mapped_column(Text)

    rating: Mapped[int | None] = mapped_column(Integer)

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

    stageEvents = relationship(
        "StageEvent",
        back_populates="application",
        cascade="all, delete-orphan",
    )

    internalNoteEntries = relationship(
        "CandidateApplicationNote",
        back_populates="application",
        cascade="all, delete-orphan",
    )

    offerLetter = relationship(
        "OfferLetter",
        back_populates="application",
        uselist=False,
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
# CANDIDATE APPLICATION NOTE
# =========================================================


class CandidateApplicationNote(Base):
    __tablename__ = "candidate_application_note"

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

    authorMemberId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updatedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization = relationship("Organization")

    application = relationship(
        "CandidateApplication",
        back_populates="internalNoteEntries",
    )

    author = relationship(
        "Member",
        back_populates="candidateApplicationNotes",
    )

    __table_args__ = (
        Index("ix_candidate_note_org_application", "organizationId", "applicationId"),
        Index("ix_candidate_note_org_author", "organizationId", "authorMemberId"),
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

# =========================================================
# STAGE EVENT
# =========================================================


class StageEvent(Base):
    __tablename__ = "stage_event"

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

    stageId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    createdByMemberId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    completedByMemberId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)

    interviewType: Mapped[InterviewType | None] = mapped_column(
        Enum(InterviewType),
        nullable=True,
    )

    assignmentMode: Mapped[str | None] = mapped_column(String(32))

    teamId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("hiring_team.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus),
        nullable=False,
        default=EventStatus.SCHEDULED,
        index=True,
    )

    scheduledStartAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    scheduledEndAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    meetingUrl: Mapped[str | None] = mapped_column(String)

    googleCalendarEventId: Mapped[str | None] = mapped_column(String(255))

    googleCalendarEventUrl: Mapped[str | None] = mapped_column(Text)

    location: Mapped[str | None] = mapped_column(String)

    notes: Mapped[str | None] = mapped_column(Text)

    emailSentAt: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

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
        back_populates="stageEvents",
    )

    application = relationship(
        "CandidateApplication",
        back_populates="stageEvents",
    )

    stage = relationship(
        "PipelineStage",
        back_populates="stageEvents",
    )

    createdBy = relationship(
        "Member",
        foreign_keys=[createdByMemberId],
        back_populates="createdStageEvents",
    )

    completedBy = relationship(
        "Member",
        foreign_keys=[completedByMemberId],
    )

    participants = relationship(
        "StageEventParticipant",
        back_populates="event",
        cascade="all, delete-orphan",
    )

    hiringTeam = relationship("HiringTeam")

    feedbacks = relationship(
        "InterviewFeedback",
        back_populates="event",
        cascade="all, delete-orphan",
    )


# =========================================================
# STAGE EVENT PARTICIPANT
# =========================================================


class StageEventParticipant(Base):
    __tablename__ = "stage_event_participant"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    eventId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stage_event.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    memberId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str | None] = mapped_column(String)

    isBackup: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    approvalStatus: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PENDING",
    )

    approvedAt: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    rejectedAt: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    scheduledTime: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # RELATIONSHIPS

    event = relationship(
        "StageEvent",
        back_populates="participants",
    )

    member = relationship(
        "Member",
        back_populates="stageEventParticipations",
    )

    __table_args__ = (
        UniqueConstraint(
            "eventId",
            "memberId",
            name="uq_stage_event_participant",
        ),
    )


# =========================================================
# INTERVIEW REJECTION RECORD
# =========================================================


class InterviewRejectionRecord(Base):
    __tablename__ = "interview_rejection_record"

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

    eventId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stage_event.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    memberId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rejectedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    event = relationship("StageEvent")
    member = relationship("Member")

    __table_args__ = (
        UniqueConstraint(
            "eventId",
            "memberId",
            name="uq_interview_rejection_event_member",
        ),
    )


# =========================================================
# INTERVIEW FEEDBACK
# =========================================================


class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

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

    eventId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stage_event.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    memberId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    outcome: Mapped[InterviewOutcome] = mapped_column(
        Enum(InterviewOutcome),
        nullable=False,
        default=InterviewOutcome.PENDING,
    )

    score: Mapped[int | None] = mapped_column(Integer)

    strengths: Mapped[str | None] = mapped_column(Text)

    weaknesses: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # RELATIONSHIPS

    organization = relationship(
        "Organization",
        back_populates="interviewFeedbacks",
    )

    event = relationship(
        "StageEvent",
        back_populates="feedbacks",
    )

    values = relationship(
        "InterviewFeedbackValue",
        back_populates="feedback",
        cascade="all, delete-orphan",
    )

    member = relationship(
        "Member",
        back_populates="interviewFeedbacks",
    )

    __table_args__ = (
        UniqueConstraint(
            "eventId",
            "memberId",
            name="uq_interview_feedback_event_member",
        ),
    )


# =========================================================
# INTERVIEW FEEDBACK VALUE
# =========================================================


class InterviewFeedbackValue(Base):
    __tablename__ = "interview_feedback_value"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    feedbackId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("interview_feedback.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    categoryId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stage_evaluation_category.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    numericValue: Mapped[float | None] = mapped_column(Float)

    textValue: Mapped[str | None] = mapped_column(Text)

    booleanValue: Mapped[bool | None] = mapped_column(Boolean)

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updatedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    feedback = relationship(
        "InterviewFeedback",
        back_populates="values",
    )

    category = relationship("StageEvaluationCategory")

    __table_args__ = (
        UniqueConstraint(
            "feedbackId",
            "categoryId",
            name="uq_interview_feedback_value_category",
        ),
    )


# =========================================================
# OFFER LETTER
# =========================================================


class OfferLetter(Base):
    __tablename__ = "offer_letter"

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
        unique=True,
        index=True,
    )

    createdByMemberId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus),
        nullable=False,
        default=OfferStatus.DRAFT,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(Text)

    salary: Mapped[float | None] = mapped_column(Float)

    currency: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="INR",
    )

    joiningDate: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
    )

    expiresAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
    )

    sentAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
    )

    respondedAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
    )

    candidateToken: Mapped[str | None] = mapped_column(
        String,
        unique=True,
    )

    pdfUrl: Mapped[str | None] = mapped_column(Text)

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
        back_populates="offerLetters",
    )

    application = relationship(
        "CandidateApplication",
        back_populates="offerLetter",
    )

    createdBy = relationship(
        "Member",
        foreign_keys=[createdByMemberId],
        back_populates="createdOfferLetters",
    )


# =========================================================
# HIRING TEAM
# =========================================================


class HiringTeam(Base):
    __tablename__ = "hiring_team"

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

    stageId: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("pipeline_stage.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(Text)

    isActive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
        back_populates="hiringTeams",
    )

    jobPosting = relationship(
        "JobPosting",
        back_populates="hiringTeams",
    )

    stage = relationship("PipelineStage", foreign_keys=[stageId])

    members = relationship(
        "HiringTeamMember",
        back_populates="hiringTeam",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("hiring_team_organizationId_idx", "organizationId"),
        Index("hiring_team_jobPostingId_idx", "jobPostingId"),
        Index("hiring_team_organizationId_isActive_idx", "organizationId", "isActive"),
    )


class HiringTeamMember(Base):
    __tablename__ = "hiring_team_member"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    hiringTeamId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hiring_team.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    memberId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # RELATIONSHIPS

    hiringTeam = relationship(
        "HiringTeam",
        back_populates="members",
    )

    member = relationship(
        "Member",
        back_populates="hiringTeamMemberships",
    )

    __table_args__ = (
        UniqueConstraint(
            "hiringTeamId",
            "memberId",
            name="uq_hiring_team_member",
        ),
    )
