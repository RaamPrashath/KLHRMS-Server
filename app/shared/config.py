"""
KL HRMS application settings.
Loads environment values safely and normalizes DATABASE_URL for asyncpg.
"""

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


def normalize_database_url(url: str) -> str:
    """
    Fixes common DB URL issues:
    - postgres:// -> postgresql://
    - sslmode=require -> ssl=require (for asyncpg)
    """
    if not url:
        return url

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query))

    # asyncpg doesn't support sslmode
    if "sslmode" in query_params:
        sslmode_value = query_params.pop("sslmode")
        if sslmode_value:
            query_params["ssl"] = sslmode_value

    new_query = urlencode(query_params)

    return urlunparse(parsed._replace(query=new_query))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────
    app_name: str = Field(default="KL HRMS API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    debug: bool = Field(default=False, alias="DEBUG")

    # ── Logging ───────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")

    # ── CORS / Hosts ──────────────────────────────────────
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )

    allowed_hosts: str = Field(
        default="localhost,127.0.0.1,testserver",
        alias="ALLOWED_HOSTS",
    )

    # ── Database ──────────────────────────────────────────
    database_url: str = Field(
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/hrms",
        ),
        alias="DATABASE_URL",
    )

    # ── Better Auth ───────────────────────────────────────
    better_auth_url: str = Field(
        default="http://localhost:3000",
        alias="BETTER_AUTH_URL",
    )

    public_app_url: str = Field(
        default=os.getenv("PUBLIC_APP_URL", os.getenv("BETTER_AUTH_URL", "http://localhost:3000")),
        alias="PUBLIC_APP_URL",
    )

    attendance_office_radius_meters: float = Field(
        default=200.0,
        alias="ATTENDANCE_OFFICE_RADIUS_METERS",
    )

    # ── External APIs ─────────────────────────────────────
    calendarific_api_key: str = Field(
        default="",
        alias="CALENDARIFIC_API_KEY",
    )

    google_client_id: str = Field(
        default=os.getenv("GOOGLE_CLIENT_ID", ""),
        alias="GOOGLE_CLIENT_ID",
    )

    google_client_secret: str = Field(
        default=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        alias="GOOGLE_CLIENT_SECRET",
    )

    resend_api_key: str = Field(
        default=os.getenv("RESEND_API_KEY", ""),
        alias="RESEND_API_KEY",
    )

    gemini_api_key: str = Field(
        default=os.getenv("GEMINI_API_KEY", ""),
        alias="GEMINI_API_KEY",
    )

    gemini_model: str = Field(
        default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        alias="GEMINI_MODEL",
    )

    resend_from_email: str = Field(
        default=os.getenv("RESEND_FROM_EMAIL", "KL HRMS <onboarding@resend.dev>"),
        alias="RESEND_FROM_EMAIL",
    )

    supabase_url: str = Field(
        default=os.getenv("SUPABASE_URL", ""),
        alias="SUPABASE_URL",
    )

    supabase_service_role_key: str = Field(
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        alias="SUPABASE_SERVICE_ROLE_KEY",
    )

    supabase_offer_bucket: str = Field(
        default=os.getenv("SUPABASE_OFFER_BUCKET", "offer-letter"),
        alias="SUPABASE_OFFER_BUCKET",
    )

    mode: str = Field(
        default=os.getenv("MODE", "development"),
        alias="MODE",
    )

    secondary_receiver: str = Field(
        default=os.getenv("SECONDARY_RECEIVER", ""),
        alias="SECONDARY_RECEIVER",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [
            host.strip()
            for host in self.allowed_hosts.split(",")
            if host.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
