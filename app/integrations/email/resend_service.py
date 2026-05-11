from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.shared.config import get_settings

RESEND_EMAILS_URL = "https://api.resend.com/emails"


class ResendEmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

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

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.settings.resend_from_email,
                    "to": [to_email],
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
