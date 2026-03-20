"""Dependencies for skill APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.skill.application.service import SkillService
from app.wiring.services import build_skill_service


def get_skill_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> SkillService:
    return build_skill_service(db=db, ctx=ctx)
