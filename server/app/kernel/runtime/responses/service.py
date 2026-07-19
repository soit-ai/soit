"""Application service for the Responses API resource/projection layer."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.kernel.commons.errors import ConflictError, KernelError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import (
    Response,
    ResponseEvent,
    ResponseInteraction,
)
from app.kernel.runtime.db.models.runs import Run, RunStep, RunStepToolCall
from app.kernel.runtime.responses.protocols import (
    ResponseEventRepositoryProtocol,
    ResponseRepositoryProtocol,
)
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.runs.tool_call_projection import project_run_tool_calls
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
        def without_transient_context(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key: without_transient_context(item)
                    for key, item in value.items()
                    if key != "_attachment_context" and key != "_context_text"
                }
            if isinstance(value, list):
                return [without_transient_context(item) for item in value]
            return value

        return {
            "input": without_transient_context(payload.input),
            "instructions": payload.instructions,
            "tools": payload.tools,
            "mcp_servers": payload.mcp_servers,
            "response_format": payload.response_format,
            "context": without_transient_context(payload.context),
            "store": payload.store,
        }

    def append_event(
        self,
        *,
        response: Response,
        event_type: str,
        payload: dict[str, Any],
        source: str = "responses",
        protocol_version: str = "soit.response.v1",
        interaction_id: str | None = None,
        visibility: str = "user",
    ) -> ResponseEvent:
        normalized_payload = dict(payload)
        if event_type.startswith("tool.call."):
            step_id = normalized_payload.get("step_id")
            run_step_id = normalized_payload.get("run_step_id")
            if step_id and run_step_id and step_id != run_step_id:
                raise ValueError("Tool-call event step identity mismatch")
            if step_id:
                normalized_payload.setdefault("run_step_id", step_id)
            elif run_step_id:
                normalized_payload["step_id"] = run_step_id
            tool_call_id = normalized_payload.get("tool_call_id")
            if response.run_id and tool_call_id:
                record_row = self.db.exec(
                    select(RunStepToolCall).where(
                        and_(
                            RunStepToolCall.run_id == response.run_id,
                            RunStepToolCall.tool_call_id == str(tool_call_id),
                            RunStepToolCall.tenant_id == self.ctx.tenant_id,
                            RunStepToolCall.workspace_id == self.ctx.workspace_id,
                        )
                    )
                ).first()
                record = (
                    record_row
                    if isinstance(record_row, RunStepToolCall)
                    else record_row[0]
                    if record_row is not None
                    else None
                )
                if record is None:
                    raise KernelError(
                        "RUNTIME_CONTRACT_VIOLATION",
                        "Tool-call event is missing a run_step_tool_calls record",
                        {
                            "run_id": response.run_id,
                            "tool_call_id": str(tool_call_id),
                        },
                    )
                normalized_payload.setdefault("run_step_tool_call_id", record.id)
                normalized_payload.setdefault("attempt_count", record.attempt_count)

        return self.event_repo.create(
            ResponseEvent(
                response_id=response.id,
                run_id=response.run_id,
                thread_id=response.thread_id,
                task_id=response.task_id,
                agent_id=response.agent_id,
                interaction_id=interaction_id,
                sequence=self.event_repo.next_sequence(response.id),
                type=event_type,
                source=source,
                protocol_version=protocol_version,
                visibility=visibility,
                payload_json=normalized_payload,
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
        failed_event_type: str | None = "response.failed",
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
        if failed_event_type:
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

    def create_response(
        self,
        payload: ResponseCreateRequest,
        *,
        emit_initial_events: bool = True,
    ) -> Response:
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
        if emit_initial_events:
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
        request_id: str | None = None,
        input_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
        emit_initial_events: bool = True,
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
                request_id=request_id or getattr(self.ctx, "request_id", None),
                model=model,
                provider=resolved_provider,
                status="queued",
                input_json=input_json or {},
                output_json={},
                usage_json={},
                metadata_json=metadata_json or {},
            )
        )
        if emit_initial_events:
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
        return project_run_tool_calls(
            db=self.db,
            ctx=self.ctx,
            run_id=response.run_id,
            steps=steps,
            response_id=response.id,
            thread_id=response.thread_id,
            task_id=response.task_id,
            agent_id=response.agent_id,
        )

    def get_response_detail(self, response_id: str):
        response = self.get_response(response_id)
        events = self.list_response_events(response_id, limit=200, offset=0)
        tool_calls = self._project_tool_calls(response)
        return response, events, tool_calls

    def get_run_timeline(self, run_id: str) -> dict[str, Any]:
        responses = self.response_repo.list_for_run(run_id)
        events = [
            event
            for event in self.event_repo.list_for_run(run_id)
            if getattr(event, "visibility", "user") == "user"
        ]
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

    def list_response_events(
        self,
        response_id: str,
        *,
        limit: int,
        offset: int,
        after_sequence: int | None = None,
        interaction_id: str | None = None,
    ) -> list[ResponseEvent]:
        self.response_repo.require(response_id)
        events = self.event_repo.list_for_response(
            response_id,
            limit=limit,
            offset=offset,
            after_sequence=after_sequence,
            interaction_id=interaction_id,
        )
        return [
            event for event in events if getattr(event, "visibility", "user") == "user"
        ]

    def get_interaction(self, interaction_id: str) -> ResponseInteraction | None:
        """Return one scoped protocol interaction mapping."""

        if self.db is None:
            return None
        query = select(ResponseInteraction).where(
            and_(
                ResponseInteraction.tenant_id == self.ctx.tenant_id,
                ResponseInteraction.workspace_id == self.ctx.workspace_id,
                ResponseInteraction.interaction_id == interaction_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, ResponseInteraction) else result[0] if result else None

    def publish_persisted_event(self, event: ResponseEvent) -> None:
        """Commit an interaction event before notifying live stream subscribers."""

        self.db.commit()
        self.trace_writer.emit_event(
            "response.event.appended",
            {
                "response_id": event.response_id,
                "interaction_id": event.interaction_id,
                "sequence": event.sequence,
                "event_type": event.type,
            },
            run_id=event.run_id,
        )

    def claim_interaction(
        self,
        *,
        interaction_id: str,
        parent_interaction_id: str | None,
        thread_id: str,
        request_hash: str,
        execution_json: dict[str, Any] | None = None,
        request_context_json: dict[str, Any] | None = None,
        kind: str = "run",
        commit: bool = True,
    ) -> tuple[ResponseInteraction, bool]:
        """Atomically claim an interaction ID before any execution side effects."""

        existing = self.get_interaction(interaction_id)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ConflictError("Interaction ID was already used with a different request")
            return existing, False
        interaction = ResponseInteraction(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            interaction_id=interaction_id,
            parent_interaction_id=parent_interaction_id,
            response_id=None,
            run_id=None,
            thread_id=thread_id,
            request_hash=request_hash,
            execution_json=execution_json or {},
            request_context_json=request_context_json or {},
            kind=kind,
            status="queued",
            created_by=self.ctx.user_id,
        )
        self.db.add(interaction)
        try:
            if commit:
                self.db.commit()
            else:
                self.db.flush()
        except IntegrityError:
            self.db.rollback()
            winner = self.get_interaction(interaction_id)
            if winner is None:
                raise
            if winner.request_hash != request_hash:
                raise ConflictError(
                    "Interaction ID was already used with a different request"
                ) from None
            return winner, False
        if commit:
            self.db.refresh(interaction)
        return interaction, True

    def claim_interaction_resume(
        self,
        *,
        parent_interaction_id: str,
        resume_interaction_id: str,
    ) -> ResponseInteraction:
        """Allow exactly one child interaction to resume an approval checkpoint."""

        result = self.db.execute(
            update(ResponseInteraction)
            .where(
                ResponseInteraction.tenant_id == self.ctx.tenant_id,
                ResponseInteraction.workspace_id == self.ctx.workspace_id,
                ResponseInteraction.interaction_id == parent_interaction_id,
                ResponseInteraction.status == "waiting_approval",
                ResponseInteraction.resume_interaction_id.is_(None),
            )
            .values(
                status="resuming",
                resume_interaction_id=resume_interaction_id,
                updated_at=utc_now(),
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            self.db.expire_all()
            claimed = self.get_interaction(parent_interaction_id)
            if claimed is None:
                raise ConflictError("Approval parent interaction disappeared during resume")
            return claimed
        self.db.expire_all()
        existing = self.get_interaction(parent_interaction_id)
        if existing is not None and existing.resume_interaction_id == resume_interaction_id:
            return existing
        raise ConflictError("Approval checkpoint is already being resumed")

    def create_interaction(
        self,
        *,
        interaction_id: str,
        parent_interaction_id: str | None,
        response: Response,
        request_hash: str,
        kind: str = "run",
    ) -> ResponseInteraction:
        """Persist the idempotency mapping for a new interaction segment."""

        existing = self.get_interaction(interaction_id)
        if existing:
            if existing.request_hash != request_hash:
                raise ConflictError("Interaction ID was already used with a different request")
            if existing.response_id is None:
                existing.response_id = response.id
                existing.run_id = response.run_id
                existing.thread_id = response.thread_id or existing.thread_id
                existing.parent_interaction_id = parent_interaction_id
                existing.kind = kind
                existing.status = "running"
                existing.updated_at = utc_now()
                self.db.add(existing)
                self.db.flush()
                self.db.refresh(existing)
            return existing
        interaction = ResponseInteraction(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            interaction_id=interaction_id,
            parent_interaction_id=parent_interaction_id,
            response_id=response.id,
            run_id=response.run_id,
            thread_id=response.thread_id or "",
            request_hash=request_hash,
            kind=kind,
            status="running",
            created_by=self.ctx.user_id,
        )
        self.db.add(interaction)
        self.db.flush()
        self.db.refresh(interaction)
        return interaction

    def update_interaction_status(self, interaction_id: str, status: str) -> None:
        """Update the lifecycle projection for a protocol interaction."""

        interaction = self.get_interaction(interaction_id)
        if not interaction or interaction.status == status:
            return
        interaction.status = status
        if status in {"succeeded", "failed", "canceled", "waiting_approval"}:
            interaction.lease_owner = None
            interaction.lease_expires_at = None
        interaction.updated_at = utc_now()
        self.db.add(interaction)
        self.db.flush()

    def fail_interaction_execution(
        self,
        interaction_id: str,
        *,
        error_code: str,
        error_message: str,
        terminal_event: dict[str, Any],
        source: str,
        protocol_version: str,
    ) -> ResponseEvent | None:
        """Terminalize a bound interaction when execution fails before streaming."""

        interaction = self.get_interaction(interaction_id)
        if interaction is None:
            return None
        if not interaction.response_id:
            self.update_interaction_status(interaction_id, "failed")
            self.db.commit()
            return None
        response = self.get_response(interaction.response_id)
        if response.status not in {"succeeded", "failed", "canceled"}:
            response = self.fail_response(
                response=response,
                error_code=error_code,
                error_message=error_message,
                source=source,
                failed_event_type=None,
            )
        run = self.db.get(Run, response.run_id) if response.run_id else None
        if run is not None and run.status not in {
            "succeeded",
            "failed",
            "canceled",
            "expired",
        }:
            self.trace_writer.update_run_status(
                run.id,
                "failed",
                output_summary=error_message,
                error_code=error_code,
                error_message=error_message,
            )
        self.update_interaction_status(interaction_id, "failed")
        existing = self.list_response_events(
            response.id,
            limit=10_000,
            offset=0,
            interaction_id=interaction_id,
        )
        prior_terminal = next(
            (event for event in existing if event.type in {"RUN_FINISHED", "RUN_ERROR"}),
            None,
        )
        if prior_terminal is not None:
            self.db.commit()
            return prior_terminal
        stored = self.append_event(
            response=response,
            event_type=str(terminal_event.get("type") or "RUN_ERROR"),
            payload=terminal_event,
            source=source,
            protocol_version=protocol_version,
            interaction_id=interaction_id,
        )
        self.publish_persisted_event(stored)
        return stored

    def save_response(self, response: Response) -> Response:
        """Persist mutable response fields."""

        return self.response_repo.update(response)

    def cancel_response(self, response_id: str, *, emit_event: bool = True) -> Response:
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
        if emit_event:
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
