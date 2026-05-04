"""
Alembic migration environment.
Uses the async PostgreSQL engine from app.core.database.
All HRMS models are imported via app.models.__init__ so
autogenerate picks up every table.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.models import Base  # noqa: F401 — imports all models for autogenerate
from app.models import *  # noqa: F401, F403

config = context.config
settings = get_settings()

# Strip +asyncpg for the sync Alembic engine
# Also convert ?ssl=require → ?sslmode=require for psycopg2 compatibility
sync_url = settings.database_url.replace("+asyncpg", "")
sync_url = sync_url.replace("?ssl=require", "?sslmode=require")
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ── Tables that Prisma owns — Alembic must never touch these ─────────────────
# Instead of a hardcoded blocklist (which breaks when new Prisma tables are added),
# we use an allowlist: only process tables that are defined in SQLAlchemy models.
# Any table NOT in Base.metadata is assumed to be Prisma-managed and is ignored.

def include_name(name, type_, parent_names):
    """
    Only include tables that Alembic owns (i.e. defined in SQLAlchemy models).
    Any table in the DB that has no corresponding SQLAlchemy model is left alone.
    This means new Prisma tables are automatically ignored without any config change.
    """
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
