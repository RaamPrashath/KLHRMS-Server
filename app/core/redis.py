import logging

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

redis_client: Redis | None = None


async def init_redis() -> None:
    global redis_client
    if not settings.redis_enabled:
        logger.info("redis.disabled")
        return

    redis_client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=False)
    try:
        await redis_client.ping()
        logger.info("redis.connected")
    except Exception as exc:
        logger.warning("redis.connection_failed", extra={"error": str(exc)})
        redis_client = None


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


async def redis_healthcheck() -> bool:
    if redis_client is None:
        return False
    try:
        await redis_client.ping()
        return True
    except Exception as exc:
        logger.warning("redis.healthcheck_failed", extra={"error": str(exc)})
        return False
