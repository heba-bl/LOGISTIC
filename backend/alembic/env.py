"""Alembic environment.

The database URL is resolved exactly like the application resolves it, so
migrations and the running API can never drift apart: if development degraded to
the SQLite fallback, `alembic upgrade head` targets that same SQLite file rather
than failing against an unreachable PostgreSQL.

Offline mode (`--sql`) always renders for the configured DATABASE_URL, which is
what you want when generating the DDL for the real PostgreSQL server.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401 - ensures every model is registered on Base.metadata

def _resolved_url() -> str:
    """The URL the application actually connected to.

    Importing the session module performs the same connectivity probe (and the
    development-only SQLite fallback) the API performs at startup.
    """
    try:
        from app.db.session import db_state

        return db_state.url
    except Exception:  # noqa: BLE001 - never let migrations fail on the probe
        return settings.DATABASE_URL


config = context.config
config.set_main_option("sqlalchemy.url", _resolved_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Offline mode renders DDL for the configured target, not the fallback.
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
