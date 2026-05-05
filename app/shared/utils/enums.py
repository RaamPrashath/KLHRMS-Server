import enum


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class WorkLocationType(str, enum.Enum):
    OFFICE = "OFFICE"
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    OFF = "OFF"