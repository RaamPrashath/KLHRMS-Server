from __future__ import annotations

from base64 import b64encode
from html import escape

import httpx
from fastapi import HTTPException

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


class ResendEmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _is_production(self) -> bool:
        return self.settings.mode.strip().lower() == "production"

    def _resolve_delivery(self, to_email: str) -> tuple[str, list[str]]:
        if self._is_production():
            return self.settings.resend_from_email, [to_email]

        fallback_email = self.settings.secondary_receiver.strip()
        if not fallback_email:
            raise HTTPException(
                status_code=400,
                detail="SECONDARY_RECEIVER must be configured when MODE is not production",
            )
        return self.settings.resend_from_email, [fallback_email]

    async def send_interview_invite(
        self,
        to_email: str,
        candidate_name: str,
        job_title: str,
        stage_name: str,
        starts_at_text: str,
        meeting_url: str,
    ) -> None:
        if not self.settings.resend_api_key:
            raise HTTPException(status_code=400, detail="Resend API key is not configured")

        subject = f"Interview invitation for {job_title}"
        body = f"""
          <p style="margin:0 0 16px;">Hello {candidate_name},</p>
          <p style="margin:0 0 16px;">Your interview for <strong>{job_title}</strong> has been scheduled.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Stage</td><td style="padding:2px 0;font-size:14px;">{stage_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Time</td><td style="padding:2px 0;font-size:14px;">{starts_at_text}</td></tr>
          </table>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{meeting_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Join Google Meet</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{meeting_url}" style="color:#00874a;">{meeting_url}</a></p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Your interview for {job_title} has been scheduled.\n"
            f"Stage: {stage_name}\n"
            f"Time: {starts_at_text}\n\n"
            f"Google Meet: {meeting_url}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_onboarding_document_request(
        self,
        *,
        to_email: str,
        candidate_name: str,
        job_title: str,
        organization_name: str,
        submission_url: str,
    ) -> None:
        subject = f"Document Submission Required for {job_title} at {organization_name}"
        safe_name = escape(candidate_name)
        safe_job = escape(job_title)
        safe_org = escape(organization_name)
        safe_url = escape(submission_url, quote=True)
        body = f"""
          <p style="margin:0 0 16px;">Hello {safe_name},</p>
          <p style="margin:0 0 16px;">Congratulations on your selection for <strong>{safe_job}</strong> at <strong>{safe_org}</strong>!</p>
          <p style="margin:0 0 20px;">To complete your onboarding, please submit your Aadhar and PAN card documents using the link below.</p>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{safe_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Submit Documents</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{safe_url}" style="color:#00874a;">{safe_url}</a></p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Congratulations on your selection for {job_title} at {organization_name}!\n"
            f"To complete your onboarding, please submit your Aadhar and PAN card documents.\n\n"
            f"Submit Documents: {submission_url}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_onboarding_credentials(
        self,
        *,
        to_email: str,
        candidate_name: str,
        login_email: str,
        password: str,
        login_url: str,
    ) -> None:
        subject = "Your HRMS Account Credentials"
        safe_name = escape(candidate_name)
        safe_login_email = escape(login_email)
        safe_password = escape(password)
        safe_login_url = escape(login_url, quote=True)
        body = f"""
          <p style="margin:0 0 16px;">Hello {safe_name},</p>
          <p style="margin:0 0 16px;">Your HRMS account has been created. You can log in using the credentials below:</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Email</td><td style="padding:2px 0;font-size:14px;font-weight:600;">{safe_login_email}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Password</td><td style="padding:2px 0;font-size:14px;font-weight:600;">{safe_password}</td></tr>
          </table>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{safe_login_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Log in to HRMS</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">Please change your password after logging in for security purposes.</p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Your HRMS account has been created.\n"
            f"Email: {login_email}\n"
            f"Password: {password}\n\n"
            f"Log in: {login_url}\n\n"
            f"Please change your password after logging in.\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_offer_letter(
        self,
        *,
        to_email: str,
        candidate_name: str,
        job_title: str,
        organization_name: str,
        download_url: str | None,
        accept_url: str,
        reject_url: str,
        expires_at_text: str,
        attachment_pdf: bytes | None = None,
        attachment_filename: str | None = None,
    ) -> None:
        subject = f"Offer Letter for {job_title} at {organization_name}"
        safe_candidate_name = escape(candidate_name)
        safe_job_title = escape(job_title)
        safe_organization_name = escape(organization_name)
        safe_expires_at_text = escape(expires_at_text)
        safe_accept_url = escape(accept_url, quote=True)
        safe_reject_url = escape(reject_url, quote=True)
        download_html = ""
        download_text = ""
        if download_url:
            safe_download_url = escape(download_url, quote=True)
            download_html = f"""
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 18px;">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{safe_download_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Download offer letter</a>
              </td>
            </tr>
          </table>
            """
            download_text = f"Download offer letter: {download_url}\n"
        body = f"""
          <p style="margin:0 0 16px;">Hello {safe_candidate_name},</p>
          <p style="margin:0 0 16px;">You have received an offer letter for <strong>{safe_job_title}</strong> at <strong>{safe_organization_name}</strong>.</p>
          <p style="margin:0 0 20px;">Please review the offer letter and respond before <strong>{safe_expires_at_text}</strong>.</p>
          {download_html}
          <p style="margin:0 0 10px;">To respond directly, use one of these links:</p>
          <p style="margin:0 0 6px;"><a href="{safe_accept_url}" style="color:#00874a;font-weight:600;">Accept offer</a></p>
          <p style="margin:0 0 16px;"><a href="{safe_reject_url}" style="color:#b42318;font-weight:600;">Reject offer</a></p>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If a link does not work, copy and open it in your browser.</p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"You have received an offer letter for {job_title} at {organization_name}.\n"
            f"Please respond before {expires_at_text}.\n\n"
            f"{download_text}"
            f"Accept offer: {accept_url}\n"
            f"Reject offer: {reject_url}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        attachments = None
        if attachment_pdf:
            attachments = [
                {
                    "filename": attachment_filename or "Offer Letter.pdf",
                    "content": b64encode(attachment_pdf).decode("ascii"),
                }
            ]
        if attachments:
            await self._send_email(to_email, subject, html, text, attachments=attachments)
        else:
            await self._send_email(to_email, subject, html, text)

    async def send_stage_interview_assignment_to_interviewer(
        self,
        to_email: str,
        interviewer_name: str,
        candidate_name: str,
        candidate_email: str,
        stage_name: str,
        organization_name: str,
        starts_at_text: str,
    ) -> None:
        subject = f"Interview assigned: {candidate_name}"
        body = f"""
          <p style="margin:0 0 16px;">Hello {interviewer_name},</p>
          <p style="margin:0 0 16px;">You have been assigned an interview for <strong>{candidate_name}</strong>.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Organization</td><td style="padding:2px 0;font-size:14px;">{organization_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Stage</td><td style="padding:2px 0;font-size:14px;">{stage_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Time</td><td style="padding:2px 0;font-size:14px;">{starts_at_text}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Candidate email</td><td style="padding:2px 0;font-size:14px;">{candidate_email}</td></tr>
          </table>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {interviewer_name},\n\n"
            f"You have been assigned an interview for {candidate_name}.\n"
            f"Organization: {organization_name}\n"
            f"Stage: {stage_name}\n"
            f"Time: {starts_at_text}\n"
            f"Candidate email: {candidate_email}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_stage_interview_assignment_to_candidate(
        self,
        to_email: str,
        candidate_name: str,
        interviewer_name: str,
        organization_name: str,
        starts_at_text: str,
    ) -> None:
        subject = f"Interview scheduled with {organization_name}"
        body = f"""
          <p style="margin:0 0 16px;">Hello {candidate_name},</p>
          <p style="margin:0 0 16px;">Your interview with <strong>{organization_name}</strong> has been scheduled.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Interviewer</td><td style="padding:2px 0;font-size:14px;">{interviewer_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Time</td><td style="padding:2px 0;font-size:14px;">{starts_at_text}</td></tr>
          </table>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Your interview with {organization_name} has been scheduled.\n"
            f"Interviewer: {interviewer_name}\n"
            f"Time: {starts_at_text}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_interview_rescheduled(
        self,
        to_email: str,
        candidate_name: str,
        job_title: str,
        stage_name: str,
        starts_at_text: str,
        meeting_url: str,
    ) -> None:
        if not self.settings.resend_api_key:
            raise HTTPException(status_code=400, detail="Resend API key is not configured")

        subject = f"Interview rescheduled – {job_title}"
        body = f"""
          <p style="margin:0 0 16px;">Hello {candidate_name},</p>
          <p style="margin:0 0 16px;">Your interview for <strong>{job_title}</strong> has been <strong>rescheduled</strong>.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Stage</td><td style="padding:2px 0;font-size:14px;">{stage_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">New time</td><td style="padding:2px 0;font-size:14px;">{starts_at_text}</td></tr>
          </table>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{meeting_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Join Google Meet</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{meeting_url}" style="color:#00874a;">{meeting_url}</a></p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Your interview for {job_title} has been rescheduled.\n"
            f"Stage: {stage_name}\n"
            f"New time: {starts_at_text}\n\n"
            f"Google Meet: {meeting_url}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_interview_meeting_ready(
        self,
        to_email: str,
        candidate_name: str,
        job_title: str,
        meeting_url: str,
    ) -> None:
        if not self.settings.resend_api_key:
            raise HTTPException(status_code=400, detail="Resend API key is not configured")

        subject = f"Your interview for {job_title} is ready"
        body = f"""
          <p style="margin:0 0 16px;">Hello {candidate_name},</p>
          <p style="margin:0 0 20px;">Your interview for <strong>{job_title}</strong> is ready to join.</p>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{meeting_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Join Google Meet</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{meeting_url}" style="color:#00874a;">{meeting_url}</a></p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Your interview for {job_title} is ready to join.\n\n"
            f"Google Meet: {meeting_url}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_reassignment_notification_to_hr(
        self,
        to_email: str,
        interviewer_name: str,
        interviewer_email: str,
        candidate_name: str,
        stage_name: str,
        organization_name: str,
        reason: str,
    ) -> None:
        subject = f"Interview reassignment request - {candidate_name} for {stage_name}"
        body = f"""
          <p style="margin:0 0 16px;">Hello HR Team,</p>
          <p style="margin:0 0 16px;">An interviewer has requested reassignment for an interview.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Candidate</td><td style="padding:2px 0;font-size:14px;">{candidate_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Stage</td><td style="padding:2px 0;font-size:14px;">{stage_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Interviewer</td><td style="padding:2px 0;font-size:14px;">{interviewer_name} ({interviewer_email})</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Reason</td><td style="padding:2px 0;font-size:14px;">{reason}</td></tr>
          </table>
          <p style="margin:16px 0 0;">Please review and reassign this interview as appropriate.</p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello HR Team,\n\n"
            f"An interviewer has requested reassignment for an interview.\n"
            f"Candidate: {candidate_name}\n"
            f"Stage: {stage_name}\n"
            f"Interviewer: {interviewer_name} ({interviewer_email})\n"
            f"Reason: {reason}\n\n"
            f"Please review and reassign this interview as appropriate.\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_interview_slot_invitation(
        self,
        to_email: str,
        candidate_name: str,
        interviewer_name: str,
        job_title: str,
        organization_name: str,
        candidate_token: str,
        is_reschedule: bool = False,
    ) -> None:
        base_url = "http://localhost:3000"
        slot_url = f"{base_url}/interview/{candidate_token}"

        subject = (
            f"Choose a new interview time with {organization_name}"
            if is_reschedule
            else f"Choose your interview time with {organization_name}"
        )
        intro = (
            f"Your interview for <strong>{job_title}</strong> needs to be rescheduled. Please choose a new time that works best for you."
            if is_reschedule
            else f"Your interview for <strong>{job_title}</strong> has been proposed. Please choose a time that works best for you."
        )
        text_intro = (
            f"Your interview for {job_title} needs to be rescheduled."
            if is_reschedule
            else f"Your interview for {job_title} has been proposed."
        )
        body = f"""
          <p style="margin:0 0 16px;">Hello {candidate_name},</p>
          <p style="margin:0 0 16px;">{intro}</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Interviewer</td><td style="padding:2px 0;font-size:14px;">{interviewer_name}</td></tr>
          </table>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{slot_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Choose Your Interview Time</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{slot_url}" style="color:#00874a;">{slot_url}</a></p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"{text_intro}\n"
            f"Interviewer: {interviewer_name}\n\n"
            f"Please choose your preferred time here:\n"
            f"{slot_url}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_interview_slot_confirmation_to_candidate(
        self,
        to_email: str,
        candidate_name: str,
        interviewer_name: str,
        job_title: str,
        starts_at_text: str,
        meeting_url: str | None,
    ) -> None:
        subject = f"Interview confirmed — {job_title}"
        meet_block = ""
        if meeting_url:
            meet_block = f"""
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{meeting_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Join Google Meet</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{meeting_url}" style="color:#00874a;">{meeting_url}</a></p>"""
        body = f"""
          <p style="margin:0 0 16px;">Hello {candidate_name},</p>
          <p style="margin:0 0 16px;">Your interview for <strong>{job_title}</strong> has been confirmed.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Interviewer</td><td style="padding:2px 0;font-size:14px;">{interviewer_name}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Time</td><td style="padding:2px 0;font-size:14px;">{starts_at_text}</td></tr>
          </table>
          {meet_block}
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Your interview for {job_title} has been confirmed.\n"
            f"Interviewer: {interviewer_name}\n"
            f"Time: {starts_at_text}\n"
            + (f"\nGoogle Meet: {meeting_url}\n" if meeting_url else "")
            + "\n---\nKovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_interview_slot_confirmation_to_interviewer(
        self,
        to_email: str,
        interviewer_name: str,
        candidate_name: str,
        job_title: str,
        starts_at_text: str,
        meeting_url: str | None,
    ) -> None:
        subject = f"Candidate selected a time — {candidate_name}"
        meet_block = ""
        if meeting_url:
            meet_block = f"""
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{meeting_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Join Google Meet</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{meeting_url}" style="color:#00874a;">{meeting_url}</a></p>"""
        body = f"""
          <p style="margin:0 0 16px;">Hello {interviewer_name},</p>
          <p style="margin:0 0 16px;"><strong>{candidate_name}</strong> has selected a time for the <strong>{job_title}</strong> interview.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Time</td><td style="padding:2px 0;font-size:14px;">{starts_at_text}</td></tr>
          </table>
          {meet_block}
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {interviewer_name},\n\n"
            f"{candidate_name} has selected a time for the {job_title} interview.\n"
            f"Time: {starts_at_text}\n"
            + (f"\nGoogle Meet: {meeting_url}\n" if meeting_url else "")
            + "\n---\nKovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_feedback_request(
        self,
        to_email: str,
        candidate_name: str,
        job_title: str,
        interviewer_name: str | None,
        stage_name: str,
        feedback_token: str,
    ) -> None:
        base_url = self.settings.better_auth_url.rstrip("/")
        feedback_url = f"{base_url}/feedback/{feedback_token}"

        subject = f"Share your interview feedback – {job_title}"
        body = f"""
          <p style="margin:0 0 16px;">Hello {candidate_name},</p>
          <p style="margin:0 0 16px;">Thank you for interviewing for <strong>{job_title}</strong>. We'd love to hear your thoughts on the interview experience.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Interviewer</td><td style="padding:2px 0;font-size:14px;">{interviewer_name or "Team"}</td></tr>
            <tr><td style="padding:2px 0;font-size:14px;color:#6e6e73;padding-right:12px;">Stage</td><td style="padding:2px 0;font-size:14px;">{stage_name}</td></tr>
          </table>
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="border-radius:8px;" bgcolor="#00874a">
                <a href="{feedback_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-size:14px;font-weight:500;">Share Your Feedback</a>
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 0;font-size:13px;color:#86868b;">If the button does not work, open this link:<br /><a href="{feedback_url}" style="color:#00874a;">{feedback_url}</a></p>
        """
        html = _email_wrapper(body)
        text = (
            f"Kovan Labs\n\n"
            f"Hello {candidate_name},\n\n"
            f"Thank you for interviewing for {job_title}. We'd love to hear your thoughts.\n"
            f"Interviewer: {interviewer_name or 'Team'}\n"
            f"Stage: {stage_name}\n\n"
            f"Share your feedback here:\n"
            f"{feedback_url}\n\n"
            f"---\n"
            f"Kovan Labs\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html: str,
        text: str,
        *,
        attachments: list[dict[str, str]] | None = None,
    ) -> None:
        if not self.settings.resend_api_key:
            raise HTTPException(status_code=400, detail="Resend API key is not configured")

        from_email, recipient_list = self._resolve_delivery(to_email)

        payload: dict[str, object] = {
            "from": from_email,
            "to": recipient_list,
            "subject": subject,
            "html": html,
            "text": text,
        }
        if attachments:
            payload["attachments"] = attachments

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=self._error_message(response))

    def _error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return "Interview email sending failed"
        message = payload.get("message")
        if isinstance(message, str) and message:
            return message
        return "Interview email sending failed"
