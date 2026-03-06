"""Alembic environment configuration."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.db.session import get_engine
from app.kernel.trace.models import Run, RunStep, RunArtifact, RunCostEntry
from app.kernel.observability.idempotency import IdempotencyKey  # noqa: F401
from app.modules.identity.domain import models as identity_models  # noqa: F401
from app.modules.security.domain import models as security_models  # noqa: F401
from app.modules.secrets.domain import models as secrets_models  # noqa: F401
from app.modules.dataset.domain import models as dataset_models  # noqa: F401
from app.modules.chat.domain import models as chat_models  # noqa: F401
from app.modules.memory.domain import models as memory_models  # noqa: F401
from app.modules.pluginmarket.domain import models as pluginmarket_models  # noqa: F401
from app.modules.appcenter.domain import models as appcenter_models  # noqa: F401
from app.modules.notification.domain import models as notification_models  # noqa: F401
from app.modules.modelhub.domain import models as modelhub_models  # noqa: F401
from sqlmodel import SQLModel

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = SQLModel.metadata

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
    """Run migrations in 'online' mode."""
    connectable = get_engine()

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
