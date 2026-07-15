"""Application service for the Responses API resource/projection layer."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import RunStep
from app.kernel.runtime.responses.protocols import (
    ResponseEventRepositoryProtocol,
    ResponseRepositoryProtocol,
)
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.status import (
    RuntimeTransitionError,
    validate_response_transition,
)


class ResponseService:
    """Manage response resources and projections on top of run execution data."""

    def __init__(
        self,
        *,
        db: Session,
        ctx: RequestContext,
        response_repo: ResponseRepositoryProtocol,
        event_repo: ResponseEventRepositoryProtocol,
        trace_writer: TraceWriter,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.response_repo = response_repo
        self.event_repo = event_repo
        self.trace_writer = trace_writer

    def _resolve_thread_id(self, payload: ResponseCreateRequest) -> str | None:
        return payload.thread_id

    def _resolve_provider(self, payload: ResponseCreateRequest) -> str | None:
        if payload.provider:
            return payload.provider
        if payload.model and payload.model.startswith("model:"):
            parts = payload.model.split(":")
            if len(parts) >= 3:
                return parts[1]
        return None

    def _normalize_input(self, payload: ResponseCreateRequest) -> dict[str, Any]:
        return {
            "input": payload.input,
            "instructions": payload.instructions,
            "tools": payload.tools,
            "mcp_servers": payload.mcp_servers,
            "response_format": payload.response_format,
            "context": payload.context,
            "store": payload.store,
            "stream": payload.stream,
        }

    def append_event(
        self,
        *,
        response: Response,
        event_type: str,
        payload: dict[str, Any],
        source: str = "responses",
    ) -> ResponseEvent:
        return self.event_repo.create(
            ResponseEvent(
                response_id=response.id,
                run_id=response.run_id,
                thread_id=response.thread_id,
                task_id=response.task_id,
                agent_id=response.agent_id,
                sequence=self.event_repo.next_sequence(response.id),
                type=event_type,
                source=source,
                payload_json=payload,
            )
        )

    def _transition_response(
        self,
        response: Response,
        target_status: str,
        **values: Any,
    ) -> Response:
        """Atomically transition a scoped response projection."""

        old_status = response.status
        normalized = validate_response_transition(old_status, target_status)
        if old_status == normalized:
            return response

        if self.db is None:
            response.status = normalized
            for key, value in values.items():
                setattr(response, key, value)
            response.error_code = values.get("error_code", response.error_code)
            response.error_message = values.get("error_message", response.error_message)
            return self.response_repo.update(response)

        values.update(
            {
                "status": normalized,
                "updated_at": utc_now(),
                "updated_by": self.ctx.user_id,
            }
        )
        result = self.db.execute(
            update(Response)
            .where(
                Response.id == response.id,
                Response.tenant_id == self.ctx.tenant_id,
                Response.workspace_id == self.ctx.workspace_id,
                Response.status == old_status,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.db.expire_all()
            current = self.response_repo.require(response.id)
            if current.status == normalized:
                return current
            validate_response_transition(current.status, normalized)
            raise RuntimeTransitionError(
                f"Concurrent response transition rejected: {old_status} -> {normalized}"
            )
        self.db.expire(response)
        self.db.refresh(response)
        return response

    def mark_running(self, response: Response) -> Response:
        """Mark a response as actively executing."""

        return self._transition_response(
            response,
            "running",
            error_code=None,
            error_message=None,
        )

    def complete_response(
        self,
        *,
        response: Response,
        output_json: dict[str, Any],
        usage_json: dict[str, Any] | None = None,
        source: str = "responses",
        output_event_type: str | None = "response.output_text.done",
        output_event_payload: dict[str, Any] | None = None,
        completed_event_type: str | None = "response.succeeded",
        completed_event_payload: dict[str, Any] | None = None,
    ) -> Response:
        """Persist a completed response and append semantic completion events."""

        response = self._transition_response(
            response,
            "succeeded",
            output_json=output_json or {},
            usage_json=usage_json or {},
            completed_at=utc_now(),
            error_code=None,
            error_message=None,
        )
        if output_event_type:
            self.append_event(
                response=response,
                event_type=output_event_type,
                payload=output_event_payload
                or {
                    "response_id": response.id,
                    "run_id": response.run_id,
                    "output": response.output_json,
                    "usage": response.usage_json,
                },
                source=source,
            )
        if completed_event_type:
            self.append_event(
                response=response,
                event_type=completed_event_type,
                payload=completed_event_payload
                or {
                    "response_id": response.id,
                    "run_id": response.run_id,
                    "status": response.status,
                    "usage": response.usage_json,
                },
                source=source,
            )
        return response

    def fail_response(
        self,
        *,
        response: Response,
        error_code: str,
        error_message: str,
        source: str = "responses",
        failed_event_type: str = "response.failed",
        failed_event_payload: dict[str, Any] | None = None,
    ) -> Response:
        """Persist a failed response and append a semantic failure event."""

        response = self._transition_response(
            response,
            "failed",
            completed_at=utc_now(),
            error_code=error_code,
            error_message=(error_message or "")[:8192],
        )
        self.append_event(
            response=response,
            event_type=failed_event_type,
            payload=failed_event_payload
            or {
                "response_id": response.id,
                "run_id": response.run_id,
                "status": response.status,
                "error": {"code": response.error_code, "message": response.error_message},
            },
            source=source,
        )
        return response

    def create_response(self, payload: ResponseCreateRequest) -> Response:
        thread_id = self._resolve_thread_id(payload)
        provider = self._resolve_provider(payload)
        run = self.trace_writer.create_run(
            mode="response",
            kind="response",
            subject_kind="thread" if thread_id else "agent" if payload.agent_id else "response",
            subject_id=thread_id or payload.agent_id,
            input_summary=str(payload.input)[:8192] if payload.input is not None else None,
        )

        response = self.response_repo.create(
            Response(
                thread_id=thread_id,
                task_id=payload.task_id,
                agent_id=payload.agent_id,
                run_id=run.id,
                request_id=getattr(self.ctx, "request_id", None),
                model=payload.model,
                provider=provider,
                status="queued",
                input_json=self._normalize_input(payload),
                output_json={},
                usage_json={},
                metadata_json=payload.metadata or {},
            )
        )
        self.append_event(
            response=response,
            event_type="response.created",
            payload={
                "response_id": response.id,
                "run_id": response.run_id,
                "status": response.status,
                "thread_id": response.thread_id,
                "task_id": response.task_id,
                "agent_id": response.agent_id,
                "model": response.model,
                "provider": response.provider,
            },
        )
        self.append_event(
            response=response,
            event_type="response.input.added",
            payload={"input": response.input_json},
        )
        return response

    def create_linked_response(
        self,
        *,
        run_id: str,
        thread_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        input_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> Response:
        """Create a response resource linked to an existing run."""

        resolved_provider = provider
        if not resolved_provider and model and model.startswith("model:"):
            parts = model.split(":")
            if len(parts) >= 3:
                resolved_provider = parts[1]

        response = self.response_repo.create(
            Response(
                thread_id=thread_id,
                task_id=task_id,
                agent_id=agent_id,
                run_id=run_id,
                request_id=getattr(self.ctx, "request_id", None),
                model=model,
                provider=resolved_provider,
                status="queued",
                input_json=input_json or {},
                output_json={},
                usage_json={},
                metadata_json=metadata_json or {},
            )
        )
        self.append_event(
            response=response,
            event_type="response.created",
            payload={
                "response_id": response.id,
                "run_id": response.run_id,
                "status": response.status,
                "thread_id": response.thread_id,
                "task_id": response.task_id,
                "agent_id": response.agent_id,
                "model": response.model,
                "provider": response.provider,
            },
        )
        self.append_event(
            response=response,
            event_type="response.input.added",
            payload={"input": response.input_json},
        )
        return response

    def get_response(self, response_id: str) -> Response:
        return self.response_repo.require(response_id)

    def _project_tool_calls(self, response: Response) -> list[dict[str, Any]]:
        if not response.run_id:
            return []
        query = (
            select(RunStep)
            .where(
                and_(
                    RunStep.run_id == response.run_id,
                    RunStep.tenant_id == self.ctx.tenant_id,
                    RunStep.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(RunStep.created_at.asc(), RunStep.id.asc())
        )
        rows = list(self.db.exec(query).all())
        steps = [item if isinstance(item, RunStep) else item[0] for item in rows]
        projections: list[dict[str, Any]] = []
        for step in steps:
            tool_call = ((step.metrics_json or {}).get("tool_call") if isinstance(step.metrics_json, dict) else None) or {}
            if not tool_call and step.step_type != "tool":
                continue
            tool_name = tool_call.get("tool_name") or tool_call.get("tool_ref")
            if not tool_name:
                continue
            projections.append(
                {
                    "id": step.id,
                    "tenant_id": step.tenant_id,
                    "workspace_id": step.workspace_id,
                    "response_id": response.id,
                    "run_id": response.run_id,
                    "step_id": step.id,
                    "thread_id": response.thread_id,
                    "task_id": response.task_id,
                    "agent_id": response.agent_id,
                    "tool_name": tool_name,
                    "tool_type": tool_call.get("tool_type", "builtin"),
                    "status": tool_call.get("status") or step.status,
                    "arguments_json": tool_call.get("arguments") or {},
                    "result_json": tool_call.get("result") or {},
                    "metadata_json": tool_call.get("metadata") or {},
                    "error_code": tool_call.get("error_code") or step.error_code,
                    "error_message": tool_call.get("error_message") or step.error_message,
                    "started_at": step.started_at,
                    "completed_at": step.ended_at,
                    "created_at": step.created_at,
                    "updated_at": step.ended_at or step.created_at,
                }
            )
        return projections

    def get_response_detail(self, response_id: str):
        response = self.get_response(response_id)
        events = self.event_repo.list_for_response(response_id, limit=200, offset=0)
        tool_calls = self._project_tool_calls(response)
        return response, events, tool_calls

    def get_run_timeline(self, run_id: str) -> dict[str, Any]:
        responses = self.response_repo.list_for_run(run_id)
        events = self.event_repo.list_for_run(run_id)
        events_by_response: dict[str, list[ResponseEvent]] = {}
        for event in events:
            events_by_response.setdefault(event.response_id, []).append(event)
        items: list[dict[str, Any]] = []
        for response in responses:
            items.append(
                {
                    "response": response,
                    "events": events_by_response.get(response.id, []),
                    "tool_calls": self._project_tool_calls(response),
                }
            )
        return {
            "run_id": run_id,
            "items": items,
        }

    def list_response_events(self, response_id: str, *, limit: int, offset: int) -> list[ResponseEvent]:
        self.response_repo.require(response_id)
        return self.event_repo.list_for_response(response_id, limit=limit, offset=offset)

    def save_response(self, response: Response) -> Response:
        """Persist mutable response fields."""

        return self.response_repo.update(response)

    def cancel_response(self, response_id: str) -> Response:
        response = self.response_repo.require(response_id)
        if response.status in {"succeeded", "failed", "canceled"}:
            return response

        response = self._transition_response(
            response,
            "canceled",
            canceled_at=utc_now(),
            error_code="response_canceled",
            error_message="Response was canceled",
        )
        if response.run_id:
            self.trace_writer.update_run_status(
                response.run_id,
                "canceled",
                output_summary="Response canceled",
                error_code="response_canceled",
                error_message="Response was canceled",
            )
        self.append_event(
            response=response,
            event_type="response.canceled",
            payload={
                "response_id": response.id,
                "run_id": response.run_id,
                "status": response.status,
            },
        )
        return response
