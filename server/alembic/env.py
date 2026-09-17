"""Alembic environment configuration."""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import (
    Column,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    create_engine,
    pool,
)

from alembic import context
from alembic.ddl.impl import DefaultImpl

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import SQLModel

import app.kernel.runtime.db.models  # noqa: F401
import app.modules  # noqa: F401
from app.modules.modelhub.domain import models as modelhub_models  # noqa: F401
from app.settings.settings import settings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = SQLModel.metadata


def _patch_alembic_version_table_length() -> None:
    """Allow long timestamp-prefixed revision ids in alembic_version."""

    def version_table_impl(  # noqa: ARG001
        self,
        *,
        version_table: str,
        version_table_schema: str | None,
        version_table_pk: bool,
        **kw,
    ) -> Table:
        table = Table(
            version_table,
            MetaData(),
            Column("version_num", String(255), nullable=False),
            schema=version_table_schema,
        )
        if version_table_pk:
            table.append_constraint(
                PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
            )
        return table

    DefaultImpl.version_table_impl = version_table_impl


_patch_alembic_version_table_length()

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Alembic runs synchronously in its own process, so it builds its own sync
    engine from the configured URL; the application itself is async-only.
    """
    database_url = settings.database_url or ""
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
