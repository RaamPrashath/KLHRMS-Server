"""
Webhook dispatch tasks.
Queued via Redis — fires outbound webhooks for developer integrations.
"""
import logging

logger = logging.getLogger(__name__)


async def dispatch_webhook(
    organization_id: str,
    event: str,
    payload: dict,
) -> None:
    """
    Dispatch a webhook event to all registered endpoints for the organization.
    TODO: implement with httpx + retry logic.
    """
    raise NotImplementedError
