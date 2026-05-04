"""
Async PostgreSQL engine and session factory.
Compatible with asyncpg + Neon + local PostgreSQL.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Optional SSL support for Neon / cloud providers
connect_args = {}

if "ssl=require" in settings.database_url:
    connect_args["ssl"] = "require"

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug,
    connect_args=connect_args,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI DB dependency:
    - Opens session
    - Auto commits
    - Rolls back on failure
    - Closes safely
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()

        except Exception:
            await session.rollback()
            raise

        finally:
            await session.close()


async def db_healthcheck() -> bool:
    """
    DB health check for monitoring.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        return True

    except Exception as exc:
        logger.error(
            "db.healthcheck_failed",
            extra={"error": str(exc)},
        )

        return False