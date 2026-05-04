"""
KL HRMS application settings.
All values loaded from environment / .env file.
No Oracle, no MongoDB, no multi-auth-provider complexity.
"""
from functools import lru_cache
from pathlib import Path
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = Field(default="KL HRMS API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    debug: bool = Field(default=False, alias="DEBUG")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")

    # ── CORS / Hosts ──────────────────────────────────────────────────────────
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    allowed_hosts: str = Field(default="localhost,127.0.0.1,testserver", alias="ALLOWED_HOSTS")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "postgresql+asyncpg://neondb_owner:npg_DAWwZ1hzp5kS@ep-misty-union-aore5yx2-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?ssl=require"),
        alias="DATABASE_URL",
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_enabled: bool = Field(default=True, alias="REDIS_ENABLED")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=120, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")
    rate_limit_exempt_paths: str = Field(
        default="/docs,/openapi.json,/redoc,/api/v1/health",
        alias="RATE_LIMIT_EXEMPT_PATHS",
    )

    # ── Better Auth ───────────────────────────────────────────────────────────
    # URL of the Next.js app that runs Better Auth
    better_auth_url: str = Field(
        default="http://localhost:3000",
        alias="BETTER_AUTH_URL",
    )

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def rate_limit_exempt_paths_list(self) -> list[str]:
        return [p.strip() for p in self.rate_limit_exempt_paths.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
