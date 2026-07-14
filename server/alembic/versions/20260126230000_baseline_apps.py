"""Historical baseline revision for the pre-Agent schema lineage.

This revision name is preserved for Alembic history only. Active runtime
semantics have since converged on Agent/Knowledge/Workflow terminology.

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
    import app.kernel.runtime.db.models  # noqa: F401
    from app.modules.identity.domain import models as _identity_models  # noqa: F401
    from app.modules.security.domain import models as _security_models  # noqa: F401
    from app.modules.secrets.domain import models as _secrets_models  # noqa: F401
    from app.modules.knowledge.domain import models as _knowledge_models  # noqa: F401
    from app.modules.agent.domain import models as _agent_models  # noqa: F401
    from app.modules.memory.domain import models as _memory_models  # noqa: F401
    from app.modules.plugin.domain import models as _plugin_models  # noqa: F401
    from app.modules.workflow.domain import models as _workflow_models  # noqa: F401
    from app.modules.notification.domain import models as _notification_models  # noqa: F401
    from app.modules.modelhub.domain import models as _modelhub_models  # noqa: F401

    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
