"""dependencies

Secrets entry dependencies.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.secrets.application.service import SecretsService
from app.wiring.services import build_secrets_service


def get_secrets_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> SecretsService:
    """Get secrets service instance."""
    return build_secrets_service(db=db, ctx=ctx)
