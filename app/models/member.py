from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import Base, generate_uuid


class Member(Base):
    __tablename__ = "member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    organizationId: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    userId: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    roleId: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE")

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="members", overlaps="role,members")
    user = relationship("User", back_populates="members")
    role = relationship("Role", foreign_keys="[Member.roleId]", primaryjoin="Member.roleId == Role.id", overlaps="organization,members")
    departmentMembers = relationship("DepartmentMember", back_populates="member")
    teamMemberships = relationship("TeamMember", back_populates="member")

    leave_requests = relationship("LeaveRequest", foreign_keys="[LeaveRequest.memberId]", back_populates="member")
    approved_leave_requests = relationship("LeaveRequest", foreign_keys="[LeaveRequest.approvedById]", back_populates="approved_by")
    leave_balances = relationship("LeaveBalance", foreign_keys="[LeaveBalance.memberId]", back_populates="member")

    movedApplicationHistories = relationship(
        "ApplicationStageHistory",
        back_populates="movedBy",
    )

    raisedJobRequisitions = relationship(
        "JobRequisition",
        foreign_keys="JobRequisition.raisedById",
        back_populates="raisedBy",
    )

    requisitionApprovals = relationship(
        "RequisitionApproval",
        foreign_keys="RequisitionApproval.approverId",
        back_populates="approver",
    )

    createdStageEvents = relationship(
        "StageEvent",
        foreign_keys="StageEvent.createdByMemberId",
        back_populates="createdBy",
    )

    stageEventParticipations = relationship(
        "StageEventParticipant",
        foreign_keys="StageEventParticipant.memberId",
        back_populates="member",
    )

    hiringTeamMemberships = relationship(
        "HiringTeamMember",
        back_populates="member",
        cascade="all, delete-orphan",
    )

    interviewFeedbacks = relationship(
        "InterviewFeedback",
        foreign_keys="InterviewFeedback.memberId",
        back_populates="member",
    )

    candidateApplicationNotes = relationship(
        "CandidateApplicationNote",
        foreign_keys="CandidateApplicationNote.authorMemberId",
        back_populates="author",
    )

    createdOfferLetters = relationship(
        "OfferLetter",
        foreign_keys="OfferLetter.createdByMemberId",
        back_populates="createdBy",
    )

    createdEvaluationWorkspaces = relationship(
        "StageEvaluationWorkspace",
        foreign_keys="StageEvaluationWorkspace.createdByMemberId",
        back_populates="createdBy",
    )
    generatedPurchaseOrders = relationship(
        "AssetPurchaseOrder",
        foreign_keys="[AssetPurchaseOrder.generatedByMemberId]",
    )
    receivedPurchaseOrders = relationship(
        "AssetPurchaseOrder",
        foreign_keys="[AssetPurchaseOrder.recipientMemberId]",
    )

    __table_args__ = (
        UniqueConstraint("organizationId", "userId", name="member_organizationId_userId_key"),
        ForeignKeyConstraint(["organizationId", "roleId"], ["role.organizationId", "role.id"]),
        Index("member_organizationId_idx", "organizationId"),
        Index("member_userId_idx", "userId"),
    )
