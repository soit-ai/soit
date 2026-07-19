""" dependencies

Agent entry dependencies.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Protocol

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlmodel import Session as SQLModelSession

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import Response
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.middleware.auth import get_current_context
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.service import AgentService
from app.modules.agent.runtime.emitter import EventEmitter
from app.modules.memory.application.service import MemoryService
from app.wiring import get_container
from app.wiring.services import build_agent_service, build_memory_service

AgentResponseStarted = Callable[[Response, ResponseService], Awaitable[None]]


class AgentStreamExecutor(Protocol):
    """Execute an Agent stream in a session detached from the HTTP stream."""

    def __call__(
        self,
        agent_id: str,
        inputs: dict[str, Any],
        event_emitter: EventEmitter,
        on_response_started: AgentResponseStarted | None = None,
        response_metadata: dict[str, Any] | None = None,
    ) -> Awaitable[dict[str, Any]]: ...


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


def get_agent_stream_executor(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentStreamExecutor:
    """Build stream executions on a session independent from the SSE request."""

    bind = db.get_bind()

    async def execute(
        agent_id: str,
        inputs: dict[str, Any],
        event_emitter: EventEmitter,
        on_response_started: AgentResponseStarted | None = None,
        response_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with SQLModelSession(bind=bind, expire_on_commit=False) as worker_db:
            service = build_agent_service(db=worker_db, ctx=ctx)
            try:
                result = await service.execute_agent_streaming(
                    agent_id,
                    inputs,
                    event_emitter,
                    on_response_started=on_response_started,
                    response_metadata=response_metadata,
                )
            except Exception as exc:
                # The application service has already written terminal failure or
                # cancellation evidence. Persist it before propagating the error.
                await event_emitter(
                    "agent.interaction.failed",
                    {
                        "code": getattr(exc, "code", None) or "agent_execution_failed",
                        "message": "Agent execution failed",
                    },
                )
                worker_db.commit()
                raise
            await event_emitter("agent.interaction.finished", {"result": result})
            worker_db.commit()
            return result

    return execute
