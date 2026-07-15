""" dependencies

Agent entry dependencies.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.runs.writer import TraceWriter
from app.middleware.auth import get_current_context
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.service import AgentService
from app.modules.memory.application.service import MemoryService
from app.wiring import get_container
from app.wiring.services import build_agent_service, build_memory_service


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


def get_agent_application_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentApplicationService:
    """Get agent application service instance."""
    return build_agent_service(db=db, ctx=ctx)
