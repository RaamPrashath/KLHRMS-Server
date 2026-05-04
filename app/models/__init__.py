# Import all models here so Alembic autogenerate picks them up.
# Modules are added incrementally as features are built.
from app.models.base import Base, HRMSBase  # noqa: F401
from app.models.hrms_role import HRMSRole  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.department import Department  # noqa: F401
from app.models.weekly_plan import WeeklyPlan  # noqa: F401
# Employee and Attendance models have been removed as requested
