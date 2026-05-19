from sqlalchemy import DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import Base, generate_uuid


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    logo: Mapped[str | None] = mapped_column(String(512))

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    members = relationship("Member", back_populates="organization", overlaps="role,members")
    roles = relationship("Role", back_populates="organization")
    candidates = relationship(
        "Candidate",
        back_populates="organization",
    )

    candidateApplications = relationship(
        "CandidateApplication",
        back_populates="organization",
    )

    pipelineStages = relationship(
        "PipelineStage",
        back_populates="organization",
    )

    stageEvaluationCategories = relationship(
        "StageEvaluationCategory",
        back_populates="organization",
    )

    stageEvaluationWorkspaces = relationship(
        "StageEvaluationWorkspace",
        back_populates="organization",
    )

    jobPostings = relationship(
        "JobPosting",
        back_populates="organization",
    )

    applicationStageHistories = relationship(
        "ApplicationStageHistory",
        back_populates="organization",
    )

    jobRequisitions = relationship(
        "JobRequisition",
        back_populates="organization",
    )

    requisitionApprovals = relationship(
        "RequisitionApproval",
        back_populates="organization",
    )

    requisitionActivityLogs = relationship(
        "RequisitionActivityLog",
        back_populates="organization",
    )

    stageEvents = relationship(
        "StageEvent",
        back_populates="organization",
    )

    interviewFeedbacks = relationship(
        "InterviewFeedback",
        back_populates="organization",
    )

    offerLetters = relationship(
        "OfferLetter",
        back_populates="organization",
    )

    hiringTeams = relationship(
        "HiringTeam",
        back_populates="organization",
    )

    __table_args__ = (
        UniqueConstraint("slug", name="organization_slug_key"),
    )
