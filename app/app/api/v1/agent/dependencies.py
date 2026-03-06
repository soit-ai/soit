""" dependencies

Agent entry dependencies.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.agent.application.service import AgentService
from app.modules.agent.application.app_facade import AgentAppFacadeService
from app.modules.memory.application.service import MemoryService
from app.wiring import get_container
from app.kernel.trace.writer import TraceWriter
from app.wiring.services import build_memory_service, build_agent_app_service


def get_agent_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentService:
    """Get agent service instance."""
    container = get_container()
    trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
    llm_port = container.get_llm_port(ctx=ctx, trace_writer=trace_writer)
    tool_port = container.get_tool_port(ctx=ctx, trace_writer=trace_writer)
    memory_service: MemoryService = build_memory_service(db=db, ctx=ctx)
    return AgentService(
        db=db,
        ctx=ctx,
        llm_port=llm_port,
        tool_port=tool_port,
        memory_service=memory_service,
        trace_writer=trace_writer,
    )


def get_agent_app_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentAppFacadeService:
    """Get agent app facade service instance."""
    return build_agent_app_service(db=db, ctx=ctx)
