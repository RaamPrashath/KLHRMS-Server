from __future__ import annotations

import html

import httpx

from app.models.member import Member
from app.models.recruitment import JobRequisition
from app.shared.config import get_settings

RESEND_EMAILS_URL = "https://api.resend.com/emails"


def _requisition_link(org_slug: str, req_id: str) -> str:
    base_url = get_settings().better_auth_url.rstrip("/")
    return f"{base_url}/{org_slug}/jobs/{req_id}"


async def _send_email(to_email: str, subject: str, html_body: str, text: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        return

    recipient = to_email
    if settings.mode.strip().lower() != "production":
        if not settings.secondary_receiver.strip():
            return
        recipient = settings.secondary_receiver.strip()

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.resend_from_email,
                    "to": [recipient],
                    "subject": subject,
                    "html": html_body,
                    "text": text,
                },
            )
    except httpx.HTTPError:
        return


async def send_requisition_submitted(
    requisition: JobRequisition,
    org_slug: str,
    approvers: list[Member],
    raiser_name: str,
) -> None:
    title = html.escape(requisition.title)
    escaped_raiser = html.escape(raiser_name)
    link = html.escape(_requisition_link(org_slug, requisition.id))
    req_number = html.escape(str(requisition.requisitionNumber or ""))
    for approver in approvers:
        if approver.user is None or not approver.user.email:
            continue
        await _send_email(
            approver.user.email,
            f"[Action Required] Requisition Submitted: {requisition.title}",
            f"""
            <p><strong>{escaped_raiser}</strong> has submitted a job requisition for approval.</p>
            <p><strong>Title:</strong> {title}</p>
            <p><strong>Requisition:</strong> {req_number}</p>
            <p><a href="{link}">Review Requisition</a></p>
            """,
            (
                f"{raiser_name} has submitted a job requisition for approval.\n"
                f"Title: {requisition.title}\n"
                f"Requisition: {requisition.requisitionNumber or ''}\n"
                f"Review: {_requisition_link(org_slug, requisition.id)}\n"
            ),
        )


async def send_requisition_decided(
    requisition: JobRequisition,
    org_slug: str,
    raiser: Member,
    decision: str,
    comment: str | None = None,
) -> None:
    if raiser.user is None or not raiser.user.email:
        return

    status_text = "Approved" if decision == "APPROVED" else "Rejected"
    escaped_title = html.escape(requisition.title)
    escaped_status = html.escape(status_text.lower())
    escaped_comment = html.escape(comment) if comment else ""
    comment_html = f"<p><strong>Comment:</strong> {escaped_comment}</p>" if comment else ""
    link = html.escape(_requisition_link(org_slug, requisition.id))
    comment_text = f"Comment: {comment}\n" if comment else ""

    await _send_email(
        raiser.user.email,
        f"Requisition {status_text}: {requisition.title}",
        f"""
        <p>Your requisition <strong>{escaped_title}</strong> has been
        <strong>{escaped_status}</strong>.</p>
        {comment_html}
        <p><a href="{link}">View Requisition</a></p>
        """,
        (
            f"Your requisition {requisition.title} has been {status_text.lower()}.\n"
            f"{comment_text}"
            f"View: {_requisition_link(org_slug, requisition.id)}\n"
        ),
    )
