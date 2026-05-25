from __future__ import annotations

import html

import httpx

from app.models.member import Member
from app.models.recruitment import JobRequisition
from app.shared.config import get_settings

RESEND_EMAILS_URL = "https://api.resend.com/emails"

EMAIL_HEAD = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@300;400;500;600;700&display=swap');
  </style>
</head>
<body style="margin:0;padding:0;background:#f5f5f7;font-family:'Figtree','Inter','Segoe UI',Arial,sans-serif;">"""


def _email_wrapper(content: str) -> str:
    return f"""\
{EMAIL_HEAD}
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f7;padding:40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;">
          <tr>
            <td style="padding:32px 40px 0;">
              <div style="font-size:22px;font-weight:700;color:#1d1d1f;letter-spacing:-0.5px;">Kovan Labs</div>
              <hr style="border:none;border-top:1px solid #e5e5e7;margin:24px 0;" />
            </td>
          </tr>
          <tr>
            <td style="padding:0 40px 32px;font-size:15px;line-height:1.6;color:#1d1d1f;font-weight:400;">
              {content}
            </td>
          </tr>
          <tr>
            <td style="background:#f5f5f7;padding:24px 40px;font-size:13px;color:#86868b;text-align:center;">
              <p style="margin:0 0 4px;font-weight:600;color:#6e6e73;">Kovan Labs</p>
              <p style="margin:0;">&copy; 2026 Kovan Labs. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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
        body = f"""
          <p style="margin:0 0 16px;">Hello,</p>
          <p style="margin:0 0 16px;"><strong>{escaped_raiser}</strong> has submitted a job requisition for approval.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Title</td><td style="padding:2px 0;font-size:14px;">{title}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Requisition</td><td style="padding:2px 0;font-size:14px;">{req_number}</td></tr>
          </table>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{link}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Review Requisition</a>
              </td>
            </tr>
          </table>
        """
        await _send_email(
            approver.user.email,
            f"[Action Required] Requisition Submitted: {requisition.title}",
            _email_wrapper(body),
            (
                f"Kovan Labs\n\n"
                f"Hello,\n\n"
                f"{raiser_name} has submitted a job requisition for approval.\n"
                f"Title: {requisition.title}\n"
                f"Requisition: {requisition.requisitionNumber or ''}\n\n"
                f"Review: {_requisition_link(org_slug, requisition.id)}\n\n"
                f"---\n"
                f"Kovan Labs\n"
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

    body = f"""
      <p style="margin:0 0 16px;">Hello,</p>
      <p style="margin:0 0 16px;">Your requisition <strong>{escaped_title}</strong> has been <strong>{escaped_status}</strong>.</p>
      {comment_html}
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0 0;">
        <tr>
          <td style="border-radius:8px;" bgcolor="#00874a">
            <a href="{link}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">View Requisition</a>
          </td>
        </tr>
      </table>
    """
    await _send_email(
        raiser.user.email,
        f"Requisition {status_text}: {requisition.title}",
        _email_wrapper(body),
        (
            f"Kovan Labs\n\n"
            f"Hello,\n\n"
            f"Your requisition {requisition.title} has been {status_text.lower()}.\n"
            f"{comment_text}"
            f"View: {_requisition_link(org_slug, requisition.id)}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        ),
    )
