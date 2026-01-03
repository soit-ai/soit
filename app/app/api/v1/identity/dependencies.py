""" dependencies

Identity entrypoint dependencies.
"""

from sqlalchemy.orm import Session
from fastapi import Depends

from app.infra.db.session import get_db
from app.modules.identity.application.service import IdentityService
from app.wiring.services import build_identity_service


def get_identity_service(
    db: Session = Depends(get_db),
) -> IdentityService:
    """Get identity service instance."""
    return build_identity_service(db=db)
