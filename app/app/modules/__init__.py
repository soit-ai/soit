"""Module loader for SQLModel metadata registration."""

# Import domain models to register tables in SQLModel.metadata.
# Keep imports minimal to avoid heavy side effects.
from app.modules.appcenter.domain import models as appcenter_models  # noqa: F401
from app.modules.chat.domain import models as chat_models  # noqa: F401
from app.modules.dataset.domain import models as dataset_models  # noqa: F401
from app.modules.identity.domain import models as identity_models  # noqa: F401
from app.modules.memory.domain import models as memory_models  # noqa: F401
from app.modules.security.domain import models as security_models  # noqa: F401
from app.modules.notification.domain import models as notification_models  # noqa: F401
from app.modules.secrets.domain import models as secrets_models  # noqa: F401
