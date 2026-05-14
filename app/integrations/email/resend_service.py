from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.shared.config import get_settings

RESEND_EMAILS_URL = "https://api.resend.com/emails"


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
        html = f"""
        <div style="font-family:Inter,Arial,sans-serif;line-height:1.5;color:#1d1d1f">
          <p>Hello {candidate_name},</p>
          <p>Your interview for <strong>{job_title}</strong> has been scheduled.</p>
          <p><strong>Stage:</strong> {stage_name}<br />
          <strong>Time:</strong> {starts_at_text}</p>
          <p>
            <a href="{meeting_url}" style="display:inline-block;background:#00874a;color:#ffffff;text-decoration:none;padding:10px 14px;border-radius:8px">
              Join Google Meet
            </a>
          </p>
          <p>If the button does not work, open this link:<br />
          <a href="{meeting_url}">{meeting_url}</a></p>
        </div>
        """
        text = (
            f"Hello {candidate_name},\n\n"
            f"Your interview for {job_title} has been scheduled.\n"
            f"Stage: {stage_name}\n"
            f"Time: {starts_at_text}\n"
            f"Google Meet: {meeting_url}\n"
        )
        from_email, recipient_list = self._resolve_delivery(to_email)

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_email,
                    "to": recipient_list,
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
            )

        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=self._error_message(response))

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
        html = f"""
        <div style="font-family:Inter,Arial,sans-serif;line-height:1.5;color:#1d1d1f">
          <p>Hello {interviewer_name},</p>
          <p>You have been assigned an interview for <strong>{candidate_name}</strong>.</p>
          <p><strong>Organization:</strong> {organization_name}<br />
          <strong>Stage:</strong> {stage_name}<br />
          <strong>Time:</strong> {starts_at_text}<br />
          <strong>Candidate email:</strong> {candidate_email}</p>
        </div>
        """
        text = (
            f"Hello {interviewer_name},\n\n"
            f"You have been assigned an interview for {candidate_name}.\n"
            f"Organization: {organization_name}\n"
            f"Stage: {stage_name}\n"
            f"Time: {starts_at_text}\n"
            f"Candidate email: {candidate_email}\n"
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
        html = f"""
        <div style="font-family:Inter,Arial,sans-serif;line-height:1.5;color:#1d1d1f">
          <p>Hello {candidate_name},</p>
          <p>Your interview with <strong>{organization_name}</strong> has been scheduled.</p>
          <p><strong>Interviewer:</strong> {interviewer_name}<br />
          <strong>Time:</strong> {starts_at_text}</p>
        </div>
        """
        text = (
            f"Hello {candidate_name},\n\n"
            f"Your interview with {organization_name} has been scheduled.\n"
            f"Interviewer: {interviewer_name}\n"
            f"Time: {starts_at_text}\n"
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
        html = f"""
        <div style="font-family:Inter,Arial,sans-serif;line-height:1.5;color:#1d1d1f">
          <p>Hello HR Team,</p>
          <p>An interviewer has requested reassignment for an interview.</p>
          <p><strong>Candidate:</strong> {candidate_name}<br />
          <strong>Stage:</strong> {stage_name}<br />
          <strong>Interviewer:</strong> {interviewer_name} ({interviewer_email})<br />
          <strong>Reason:</strong> {reason}</p>
          <p>Please review and reassign this interview as appropriate.</p>
        </div>
        """
        text = (
            f"Hello HR Team,\n\n"
            f"An interviewer has requested reassignment for an interview.\n"
            f"Candidate: {candidate_name}\n"
            f"Stage: {stage_name}\n"
            f"Interviewer: {interviewer_name} ({interviewer_email})\n"
            f"Reason: {reason}\n\n"
            f"Please review and reassign this interview as appropriate.\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def send_interview_backup_notification(
        self,
        to_email: str,
        backup_name: str,
        candidate_name: str,
        stage_name: str,
        starts_at_text: str,
        organization_name: str,
    ) -> None:
        subject = f"You are a backup interviewer for {candidate_name} - {organization_name}"
        html = f"""
        <div style="font-family:Inter,Arial,sans-serif;line-height:1.5;color:#1d1d1f">
          <p>Hello {backup_name},</p>
          <p>You have been added as a backup interviewer for an upcoming interview at <strong>{organization_name}</strong>.</p>
          <p><strong>Candidate:</strong> {candidate_name}<br />
          <strong>Stage:</strong> {stage_name}<br />
          <strong>Time:</strong> {starts_at_text}</p>
          <p>You will be contacted if the primary interviewer is unavailable.</p>
        </div>
        """
        text = (
            f"Hello {backup_name},\n\n"
            f"You have been added as a backup interviewer for an upcoming interview at {organization_name}.\n"
            f"Candidate: {candidate_name}\n"
            f"Stage: {stage_name}\n"
            f"Time: {starts_at_text}\n\n"
            f"You will be contacted if the primary interviewer is unavailable.\n"
        )
        await self._send_email(to_email, subject, html, text)

    async def _send_email(self, to_email: str, subject: str, html: str, text: str) -> None:
        if not self.settings.resend_api_key:
            raise HTTPException(status_code=400, detail="Resend API key is not configured")

        from_email, recipient_list = self._resolve_delivery(to_email)

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_email,
                    "to": recipient_list,
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
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
