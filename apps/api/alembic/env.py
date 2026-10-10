"""Alembic environment. The application passes the database URL in."""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from issuebot.models import Base

# fileConfig would replace the redacting JSON handler and disable uvicorn loggers.
config = context.config

target_metadata = Base.metadata


def _connect_args(url: str | None) -> dict:
    if url and url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    url = config.get_main_option("sqlalchemy.url")
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_connect_args(url),
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
