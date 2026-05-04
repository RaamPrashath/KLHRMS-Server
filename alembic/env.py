from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

from app.models import Base  # noqa: F401
from app.models import *  # noqa: F401, F403

load_dotenv()

config = context.config

# Read from .env and strip +asyncpg for sync engine
db_url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Exclude Prisma's internal migration table."""
    if name == "_prisma_migrations":
        return False
    return True


def compare_index(context, metadata_index, inspector_index):
    """Skip index comparison."""
    return False


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
            compare_type=False,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()