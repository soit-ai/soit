"""Dependencies for MCP APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.integrations.mcp.application.service import MCPService
from app.wiring.services import build_mcp_service


def get_mcp_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> MCPService:
    return build_mcp_service(db=db, ctx=ctx)
