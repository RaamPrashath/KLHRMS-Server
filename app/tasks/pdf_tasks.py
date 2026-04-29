"""
PDF generation tasks.
Queued via Redis — generates payslip and offer letter PDFs asynchronously.
"""
import logging

logger = logging.getLogger(__name__)


async def generate_payslip_pdf(payslip_id: str, organization_id: str) -> str:
    """
    Generate a payslip PDF and return the storage URL.
    TODO: implement with WeasyPrint or ReportLab + S3/MinIO upload.
    """
    raise NotImplementedError


async def generate_offer_letter_pdf(employee_id: str, organization_id: str) -> str:
    """
    Generate an offer letter PDF and return the storage URL.
    TODO: implement with Jinja2 template + WeasyPrint.
    """
    raise NotImplementedError
