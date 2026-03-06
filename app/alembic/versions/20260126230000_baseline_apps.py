"""baseline apps/app_versions and core tables

Revision ID: 20260126230000_baseline_apps
Revises: 
Create Date: 2026-01-26 23:00:00
"""

from alembic import op
from sqlmodel import SQLModel

# revision identifiers, used by Alembic.
revision = "20260126230000_baseline_apps"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Import models to register SQLModel metadata.
    from app.kernel.trace import models as _trace_models  # noqa: F401
    from app.kernel.observability.idempotency import IdempotencyKey  # noqa: F401
    from app.modules.identity.domain import models as _identity_models  # noqa: F401
    from app.modules.security.domain import models as _security_models  # noqa: F401
    from app.modules.secrets.domain import models as _secrets_models  # noqa: F401
    from app.modules.dataset.domain import models as _dataset_models  # noqa: F401
    from app.modules.chat.domain import models as _chat_models  # noqa: F401
    from app.modules.memory.domain import models as _memory_models  # noqa: F401
    from app.modules.pluginmarket.domain import models as _pluginmarket_models  # noqa: F401
    from app.modules.appcenter.domain import models as _appcenter_models  # noqa: F401
    from app.modules.notification.domain import models as _notification_models  # noqa: F401
    from app.modules.modelhub.domain import models as _modelhub_models  # noqa: F401

    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
