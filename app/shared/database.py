import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.shared.config import normalize_database_url

load_dotenv()

DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", ""))
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
)

async_engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
