from __future__ import annotations

from email.utils import parseaddr
from typing import Protocol

RESEND_SANDBOX_FROM_EMAIL = "Kovan Labs <onboarding@resend.dev>"
RESEND_SANDBOX_DOMAIN = "resend.dev"


class ResendSettings(Protocol):
    mode: str
    resend_from_email: str
    secondary_receiver: str


def normalize_resend_from_email(value: str | None) -> str:
    from_email = (value or "").strip()
    return from_email or RESEND_SANDBOX_FROM_EMAIL


def resend_sender_address(from_email: str) -> str:
    return parseaddr(from_email)[1].strip().lower()


def is_resend_sandbox_sender(from_email: str) -> bool:
    address = resend_sender_address(from_email)
    if "@" not in address:
        return False
    return address.rsplit("@", 1)[1] == RESEND_SANDBOX_DOMAIN


def validate_resend_sender_for_environment(settings: ResendSettings) -> str:
    from_email = normalize_resend_from_email(settings.resend_from_email)
    if settings.mode.strip().lower() == "production" and is_resend_sandbox_sender(from_email):
        raise ValueError(
            "RESEND_FROM_EMAIL must use an address on a verified Resend domain in production. "
            "onboarding@resend.dev is only for Resend sandbox testing."
        )
    return from_email


def resolve_resend_delivery(settings: ResendSettings, to_email: str) -> tuple[str, list[str]]:
    from_email = validate_resend_sender_for_environment(settings)
    if settings.mode.strip().lower() == "production":
        return from_email, [to_email]

    fallback_email = settings.secondary_receiver.strip()
    if not fallback_email:
        raise ValueError("SECONDARY_RECEIVER must be configured when MODE is not production")
    return from_email, [fallback_email]
