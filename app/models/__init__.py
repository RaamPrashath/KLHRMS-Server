"""
All SQLAlchemy models imported here so Alembic autogenerate picks them up.
Add new model imports here as modules are built.
"""
from app.shared.lib.base_model import Base, HRMSBase  # noqa: F401
from app.models.hrms_role import HRMSRole              # noqa: F401
from app.models.weekly_plan import WeeklyPlan          # noqa: F401
