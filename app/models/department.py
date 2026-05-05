from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import Base, generate_uuid


class Department(Base):
    __tablename__ = "department"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parentDepartmentId: Mapped[str | None] = mapped_column(String(36), nullable=True)
    headMemberId: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="ACTIVE")

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    parent = relationship(
        "Department",
        foreign_keys="[Department.parentDepartmentId]",
        primaryjoin="Department.parentDepartmentId == Department.id",
        remote_side="Department.id",
        back_populates="children",
        passive_deletes=True,
    )
    children = relationship(
        "Department",
        foreign_keys="[Department.parentDepartmentId]",
        primaryjoin="Department.id == Department.parentDepartmentId",
        back_populates="parent",
    )
    members = relationship("DepartmentMember", back_populates="department")

    __table_args__ = (
        Index("department_organizationId_idx", "organizationId"),
        Index("department_organizationId_status_idx", "organizationId", "status"),
        Index("department_parentDepartmentId_idx", "parentDepartmentId"),
        Index("department_headMemberId_idx", "headMemberId"),
    )