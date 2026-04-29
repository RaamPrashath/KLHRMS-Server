# Import all models here so Alembic autogenerate picks them up.
from app.models.base import Base, HRMSBase  # noqa: F401
from app.models.hrms_role import HRMSRole  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.employee import Employee  # noqa: F401
from app.models.department import Department  # noqa: F401
from app.models.attendance import Attendance  # noqa: F401
from app.models.leave import Leave  # noqa: F401
from app.models.timesheet import Timesheet  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.recruitment import Recruitment  # noqa: F401
from app.models.payroll import Payroll  # noqa: F401
from app.models.payslip import Payslip  # noqa: F401
from app.models.asset import Asset  # noqa: F401
from app.models.helpdesk import HelpdeskTicket  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.developer import DeveloperToken  # noqa: F401
