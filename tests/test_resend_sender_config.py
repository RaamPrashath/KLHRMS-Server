from __future__ import annotations

from types import SimpleNamespace

from app.integrations.email.resend_config import (
    RESEND_SANDBOX_FROM_EMAIL,
    is_resend_sandbox_sender,
    resolve_resend_delivery,
    validate_resend_sender_for_environment,
)


def _settings(
    *,
    mode: str = "production",
    from_email: str = "Kovan Labs <hr@kovanlabs.com>",
    secondary_receiver: str = "qa@example.com",
) -> SimpleNamespace:
    return SimpleNamespace(
        mode=mode,
        resend_from_email=from_email,
        secondary_receiver=secondary_receiver,
    )


def test_resend_dev_sender_is_allowed_in_production_for_now() -> None:
    assert is_resend_sandbox_sender(RESEND_SANDBOX_FROM_EMAIL)

    assert (
        validate_resend_sender_for_environment(
            _settings(mode="production", from_email=RESEND_SANDBOX_FROM_EMAIL)
        )
        == RESEND_SANDBOX_FROM_EMAIL
    )

    assert (
        validate_resend_sender_for_environment(
            _settings(mode="development", from_email=RESEND_SANDBOX_FROM_EMAIL)
        )
        == RESEND_SANDBOX_FROM_EMAIL
    )


def test_production_delivery_uses_configured_verified_sender_and_real_recipient() -> None:
    from_email, recipients = resolve_resend_delivery(
        _settings(mode="production", from_email="Kovan Labs <hr@kovanlabs.com>"),
        "candidate@example.com",
    )

    assert from_email == "Kovan Labs <hr@kovanlabs.com>"
    assert recipients == ["candidate@example.com"]


def test_non_production_delivery_routes_to_secondary_receiver() -> None:
    from_email, recipients = resolve_resend_delivery(
        _settings(mode="development", from_email=RESEND_SANDBOX_FROM_EMAIL),
        "candidate@example.com",
    )

    assert from_email == RESEND_SANDBOX_FROM_EMAIL
    assert recipients == ["qa@example.com"]
