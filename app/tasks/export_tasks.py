"""
Data export tasks.
Queued via Redis — generates CSV/XLSX exports for reports.
"""
import logging

logger = logging.getLogger(__name__)


async def export_attendance_csv(organization_id: str, month: int, year: int) -> str:
    """Export attendance data as CSV. Returns download URL."""
    raise NotImplementedError


async def export_payroll_xlsx(organization_id: str, payroll_id: str) -> str:
    """Export payroll run as XLSX. Returns download URL."""
    raise NotImplementedError
