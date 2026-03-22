"""Module loader for SQLModel metadata registration."""

# Import domain models to register tables in SQLModel.metadata.
# Keep imports minimal to avoid heavy side effects.
from app.modules.agent.domain import models as agent_models  # noqa: F401
from app.modules.knowledge.domain import models as knowledge_storage_models  # noqa: F401
from app.modules.identity.domain import models as identity_models  # noqa: F401
from app.modules.memory.domain import models as memory_models  # noqa: F401
from app.modules.security.domain import models as security_models  # noqa: F401
from app.modules.notification.domain import models as notification_models  # noqa: F401
from app.modules.secrets.domain import models as secrets_models  # noqa: F401
from app.modules.skill.domain import models as skill_models  # noqa: F401
from app.modules.workflow.domain import models as workflow_models  # noqa: F401
from app.modules.integrations.mcp.domain import models as mcp_models  # noqa: F401
from app.modules.observability.domain import models as observability_models  # noqa: F401
from app.modules.plugin.domain import models as plugin_models  # noqa: F401
