"""Persist authoritative Agent runtime events as AG-UI interaction events."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from app.adapters.agui.responses import AgUiInteractionProtocolAdapter
from app.kernel.commons.ids import generate_ulid
from app.kernel.runtime.db.models.responses import Response
from app.kernel.runtime.db.models.threads import generate_thread_message_id
from app.kernel.runtime.responses.interaction import InteractionProtocolEvent
from app.kernel.runtime.responses.service import ResponseService


class PersistentAgUiAgentEmitter:
    """Bridge Agent execution callbacks into a durable AG-UI event stream."""

    def __init__(
        self,
        *,
        response_service: ResponseService,
        interaction_id: str,
        parent_interaction_id: str | None,
        thread_id: str,
        assistant_message_id: str | None = None,
        queue: asyncio.Queue[dict[str, Any] | None] | None = None,
        lease_guard: Callable[[], None] | None = None,
    ) -> None:
        self.response_service = response_service
        self.interaction_id = interaction_id
        self.parent_interaction_id = parent_interaction_id
        self.thread_id = thread_id
        self.queue = queue
        self.lease_guard = lease_guard
        self.protocol = AgUiInteractionProtocolAdapter()
        self.response: Response | None = None
        self.assistant_message_id = assistant_message_id or generate_thread_message_id()
        self.activity_message_id = f"activity_{generate_ulid()}"
        self.reasoning_count = 0
        self.text_started = False
        self.text_has_content = False
        self.text_ended = False
        self.terminal_emitted = False

    def _ensure_lease(self) -> None:
        if self.lease_guard is not None:
            self.lease_guard()

    async def _persist(self, event: InteractionProtocolEvent) -> None:
        self._ensure_lease()
        if self.response is None:
            raise RuntimeError("AG-UI Agent emitter is not bound to a response")
        stored = self.response_service.append_event(
            response=self.response,
            event_type=event.type,
            payload=event.payload,
            source=self.protocol.source,
            protocol_version=self.protocol.protocol_version,
            interaction_id=self.interaction_id,
        )
        self.response_service.publish_persisted_event(stored)
        if self.queue is not None:
            await self.queue.put(
                {
                    "id": f"{stored.response_id}:{stored.sequence}",
                    "data": stored.payload_json,
                }
            )

    async def bind_response(self, response: Response, *, request_hash: str = "") -> None:
        """Bind SOIT resources and emit the opening interaction events."""

        self._ensure_lease()
        response.metadata_json = {
            **(response.metadata_json or {}),
            "protocol": "ag-ui",
            "protocol_version": "0.1.19",
            "interaction_id": self.interaction_id,
            "parent_interaction_id": self.parent_interaction_id,
        }
        response = self.response_service.save_response(response)
        self.response = response
        self.response_service.create_interaction(
            interaction_id=self.interaction_id,
            parent_interaction_id=self.parent_interaction_id,
            response=response,
            request_hash=request_hash or self.interaction_id,
        )
        if self.parent_interaction_id:
            parent = self.response_service.get_interaction(self.parent_interaction_id)
            if (
                parent is not None
                and parent.status == "resuming"
                and parent.resume_interaction_id == self.interaction_id
            ):
                self.response_service.update_interaction_status(
                    self.parent_interaction_id,
                    "succeeded",
                )
        await self._persist(
            self.protocol.run_started(
                thread_id=self.thread_id,
                interaction_id=self.interaction_id,
                parent_interaction_id=self.parent_interaction_id,
            )
        )
        await self._persist(
            self.protocol.resources(response=response, interaction_id=self.interaction_id)
        )

    async def __call__(self, event: str, data: dict[str, Any]) -> None:
        self._ensure_lease()
        if event == "agent.interaction.finished":
            result = dict(data.get("result") or {})
            if result.get("status") == "waiting_approval":
                await self.interrupt(result)
            else:
                await self.complete(result)
            return
        if event == "agent.interaction.failed":
            code = str(data.get("code") or "agent_execution_failed")
            if code == "AGENT_RUN_CANCELED":
                await self.cancel()
                return
            await self._emit_failure(code=code)
            return
        if event == "agent.plan.started" or event == "agent.plan.succeeded":
            await self._persist(
                self.protocol.activity(
                    message_id=self.activity_message_id,
                    activity_type="soit.agent.plan",
                    content={
                        "schemaVersion": 1,
                        "status": "running" if event.endswith("started") else "completed",
                        **data,
                    },
                )
            )
            return
        if event == "agent.reasoning.completed":
            content = str(data.get("content") or "")
            if not content:
                return
            self.reasoning_count += 1
            message_id = (
                f"{self.assistant_message_id}_reasoning_{self.reasoning_count}"
            )
            for reasoning_event in self.protocol.reasoning_started(
                message_id=message_id
            ):
                await self._persist(reasoning_event)
            await self._persist(
                self.protocol.reasoning_content(
                    message_id=message_id,
                    delta=content,
                )
            )
            for reasoning_event in self.protocol.reasoning_ended(
                message_id=message_id
            ):
                await self._persist(reasoning_event)
            return
        if event == "agent.tool.started":
            tool_call_id = str(data.get("tool_call_id") or f"tool_{generate_ulid()}")
            tool_name = str(data.get("tool_ref") or "tool")
            await self._persist(
                self.protocol.tool_started(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    parent_message_id=self.assistant_message_id,
                )
            )
            await self._persist(
                self.protocol.tool_arguments(
                    tool_call_id=tool_call_id,
                    delta=json.dumps(data.get("arguments") or {}, ensure_ascii=False),
                )
            )
            await self._persist(self.protocol.tool_ended(tool_call_id=tool_call_id))
            await self._persist(
                self.protocol.custom(
                    "soit.tool_status",
                    {
                        "schemaVersion": 1,
                        "toolCallId": tool_call_id,
                        "toolName": tool_name,
                        "toolType": data.get("tool_type") or "builtin",
                        "status": "running",
                    },
                )
            )
            return
        if event == "agent.tool.succeeded":
            tool_call_id = str(data.get("tool_call_id") or "")
            await self._persist(
                self.protocol.tool_result(
                    message_id=f"msg_tool_{generate_ulid()}",
                    tool_call_id=tool_call_id,
                    content=json.dumps(
                        data.get("result") or data.get("error") or {},
                        ensure_ascii=False,
                    ),
                )
            )
            await self._persist(
                self.protocol.custom(
                    "soit.tool_status",
                    {
                        "schemaVersion": 1,
                        "toolCallId": tool_call_id,
                        "toolName": data.get("tool_ref") or "tool",
                        "toolType": data.get("tool_type") or "builtin",
                        "status": "completed" if data.get("success", True) else "failed",
                        "metadata": data.get("metadata") or {},
                        "error": data.get("error"),
                    },
                )
            )
            return
        if event == "agent.response.succeeded":
            if not self.text_started:
                await self._persist(
                    self.protocol.text_started(message_id=self.assistant_message_id)
                )
                self.text_started = True
            output = str(data.get("output") or "")
            if output:
                await self._persist(
                    self.protocol.text_content(
                        message_id=self.assistant_message_id,
                        delta=output,
                    )
                )
                self.text_has_content = True
            return
        if event == "agent.approval.required":
            interrupt = dict(data.get("interrupt") or {})
            await self._persist(
                self.protocol.custom(
                    "soit.approval",
                    {
                        "schemaVersion": 1,
                        "status": "pending",
                        "interrupt": interrupt,
                    },
                )
            )

    async def interrupt(self, result: dict[str, Any]) -> None:
        self._ensure_lease()
        if self.terminal_emitted:
            return
        interrupt = dict(result.get("interrupt") or {})
        self.response_service.update_interaction_status(
            self.interaction_id,
            "waiting_approval",
        )
        await self._persist(
            self.protocol.run_interrupted(
                thread_id=self.thread_id,
                interaction_id=self.interaction_id,
                interrupt=interrupt,
            )
        )
        self.terminal_emitted = True

    async def complete(self, result: dict[str, Any]) -> None:
        self._ensure_lease()
        if self.terminal_emitted:
            return
        if not self.text_started:
            await self._persist(self.protocol.text_started(message_id=self.assistant_message_id))
            self.text_started = True
            output = str(result.get("output") or "")
            if output:
                await self._persist(
                    self.protocol.text_content(
                        message_id=self.assistant_message_id,
                        delta=output,
                    )
                )
                self.text_has_content = True
        await self._persist(self.protocol.text_ended(message_id=self.assistant_message_id))
        self.text_ended = True
        for citation in result.get("citations") or []:
            await self._persist(
                self.protocol.custom(
                    "soit.source",
                    {"schemaVersion": 1, **dict(citation)},
                )
            )
        for artifact in result.get("artifacts") or []:
            await self._persist(
                self.protocol.custom(
                    "soit.artifact",
                    {"schemaVersion": 1, **dict(artifact)},
                )
            )
        usage = {
            "prompt_tokens": int(result.get("tokens_prompt") or 0),
            "completion_tokens": int(result.get("tokens_completion") or 0),
            "total_tokens": int(result.get("tokens_prompt") or 0)
            + int(result.get("tokens_completion") or 0),
        }
        await self._persist(self.protocol.usage(usage=usage, model=result.get("model")))
        await self._persist(
            self.protocol.custom(
                "soit.governance",
                {
                    "schemaVersion": 1,
                    "budgetExceeded": bool(result.get("budget_exceeded")),
                    "budgetReason": result.get("budget_reason"),
                    "costTotal": float(result.get("cost_total") or 0),
                    "failures": int(result.get("failures") or 0),
                },
            )
        )
        self.response_service.update_interaction_status(self.interaction_id, "succeeded")
        await self._persist(
            self.protocol.run_finished(
                thread_id=self.thread_id,
                interaction_id=self.interaction_id,
                result={
                    "status": "succeeded",
                    "responseId": result.get("response_id")
                    or (self.response.id if self.response else None),
                    "executionRunId": result.get("run_id"),
                    "taskId": result.get("task_id"),
                    "finishReason": result.get("finish_reason"),
                },
            )
        )
        self.terminal_emitted = True

    async def fail(self, error: Exception) -> None:
        self._ensure_lease()
        if self.terminal_emitted:
            return
        if getattr(error, "code", None) == "AGENT_RUN_CANCELED":
            await self.cancel()
            return
        await self._emit_failure(
            code=getattr(error, "code", None) or "agent_execution_failed"
        )

    async def _emit_failure(self, *, code: str) -> None:
        if self.response is None or self.terminal_emitted:
            return
        self.response_service.update_interaction_status(self.interaction_id, "failed")
        if not self.text_started:
            await self._persist(
                self.protocol.text_started(message_id=self.assistant_message_id)
            )
            self.text_started = True
        if not self.text_has_content:
            await self._persist(
                self.protocol.text_content(
                    message_id=self.assistant_message_id,
                    delta="Agent execution failed",
                )
            )
            self.text_has_content = True
        if not self.text_ended:
            await self._persist(
                self.protocol.text_ended(message_id=self.assistant_message_id)
            )
            self.text_ended = True
        await self._persist(
            self.protocol.run_error(
                code=code,
                message="Agent execution failed",
            )
        )
        self.terminal_emitted = True

    async def cancel(self) -> None:
        """Persist or forward the single cancellation terminal for this interaction."""

        self._ensure_lease()
        if self.response is None or self.terminal_emitted:
            return
        events = self.response_service.list_response_events(
            self.response.id,
            limit=10_000,
            offset=0,
        )
        existing = next(
            (
                event
                for event in reversed(events)
                if event.type == "RUN_FINISHED"
                and (event.payload_json.get("result") or {}).get("status") == "canceled"
            ),
            None,
        )
        self.response_service.update_interaction_status(self.interaction_id, "canceled")
        if existing is None:
            if self.text_started and not self.text_ended:
                await self._persist(
                    self.protocol.text_ended(message_id=self.assistant_message_id)
                )
                self.text_ended = True
            await self._persist(
                self.protocol.run_cancelled(
                    thread_id=self.thread_id,
                    interaction_id=self.interaction_id,
                )
            )
        elif self.queue is not None:
            await self.queue.put(
                {
                    "id": f"{existing.response_id}:{existing.sequence}",
                    "data": existing.payload_json,
                }
            )
            self.response_service.db.commit()
        self.terminal_emitted = True

    async def done(self) -> None:
        if self.queue is not None:
            await self.queue.put(None)
