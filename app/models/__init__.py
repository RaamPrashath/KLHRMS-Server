"""
All SQLAlchemy models imported here so Alembic autogenerate picks them up.
Add new model imports here as modules are built.

NOTE: auth_tables.py (PrismaMember, PrismaOrganization, PrismaUser) is
intentionally NOT imported here — those models use a separate _PrismaBase
and must never be managed by Alembic. Prisma owns those tables.

NOTE: hrms_role.py (HRMSRole) is no longer imported. The hrms_roles table
is superseded by Prisma's Member.hrmsRole. Alembic will no longer manage it
(the include_name guard in env.py ensures it is left untouched in the DB).
"""
from app.shared.lib.base_model import Base, HRMSBase  # noqa: F401
from app.models.weekly_plan import WeeklyPlan          # noqa: F401
from app.models.leave import (                         # noqa: F401
    EmployeeReporting,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveTypeConfig,
)
