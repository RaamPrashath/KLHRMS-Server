import enum


class LeaveRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class WorkLocationType(str, enum.Enum):
    OFFICE = "OFFICE"
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    OFF = "OFF"


class TimesheetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ActivityType(str, enum.Enum):
    DEVELOPMENT = "DEVELOPMENT"
    DESIGN = "DESIGN"
    MEETING = "MEETING"
    REVIEW = "REVIEW"
    TESTING = "TESTING"
    DOCUMENTATION = "DOCUMENTATION"
    SUPPORT = "SUPPORT"
    OTHER = "OTHER"