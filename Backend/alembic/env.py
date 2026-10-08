"""Alembic environment for running async database migrations.
- Imports all ORM models so Alembic can see their tables.
- Overrides sqlalchemy.url with the app's Settings (same .env source).
- target_metadata points to Base.metadata for autogenerate/comparison.
- run_migrations_offline emits SQL without connecting.
- run_async_migrations creates a NullPool engine, connects, runs sync migrations inside async context, then disposes.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import models so their tables register on Base.metadata before migrations run
from app.auth.models import User
from app.db import Base
from app.models.execution_log import ExecutionLog
from app.models.pipeline_template import PipelineTemplate
from app.config import settings

# Alembic Config object providing access to .ini values
config = context.config

# Set up Python logging from the config file if provided
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the app's database URL from settings instead of a static placeholder
config.set_main_option("sqlalchemy.url", settings.database_url)

# Metadata used by Alembic to compare and generate migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (no database connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations using an existing database connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations synchronously inside it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode using the async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
