"""Dependencies for governed conversation attachments."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.attachments.service import AttachmentService
from app.middleware.auth import get_current_context
from app.wiring import get_container


def get_attachment_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AttachmentService:
    storage_port = get_container().get_storage_port(ctx=ctx)
    return AttachmentService(db=db, ctx=ctx, storage_port=storage_port)
