"""Application service for the Responses API resource/projection layer."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.responses.models import Response, ResponseEvent
from app.kernel.responses.repository import ResponseEventRepository, ResponseRepository
from app.kernel.responses.schemas import ResponseCreateRequest
from app.kernel.trace.models import RunStep
from app.kernel.trace.writer import TraceWriter


class ResponseService:
    """Manage response resources and projections on top of run execution data."""

    def __init__(
        self,
        *,
        db: Session,
        ctx: RequestContext,
        response_repo: ResponseRepository,
        event_repo: ResponseEventRepository,
        trace_writer: TraceWriter,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.response_repo = response_repo
        self.event_repo = event_repo
        self.trace_writer = trace_writer

    def _resolve_thread_id(self, payload: ResponseCreateRequest) -> Optional[str]:
        return payload.thread_id

    def _resolve_provider(self, payload: ResponseCreateRequest) -> Optional[str]:
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
        thread_id: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        input_json: Optional[dict[str, Any]] = None,
        metadata_json: Optional[dict[str, Any]] = None,
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
        if response.status in {"completed", "failed", "canceled"}:
            return response

        response.status = "canceled"
        response.canceled_at = utc_now()
        response.error_code = "response_canceled"
        response.error_message = "Response was canceled"
        response = self.response_repo.update(response)
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
