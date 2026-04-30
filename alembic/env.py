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
sync_url = settings.database_url.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# 🔥 Ignore Prisma internal table
def include_object(object, name, type_, reflected, compare_to):
    if name == "_prisma_migrations":
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_index=compare_index,
        compare_type=False,
        include_object=include_object,
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
            compare_index=compare_index,
            compare_type=False,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()

def include_object(object, name, type_, reflected, compare_to):
    if name == "_prisma_migrations":
        return False
    return True


def compare_index(context, metadata_index, inspector_index):
    return False

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()