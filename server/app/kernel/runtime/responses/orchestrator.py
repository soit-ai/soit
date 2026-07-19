"""Response resource coordinator for semantic API flows."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.kernel.commons.errors import ConflictError, ValidationError
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatStreamChunk,
    HostedArtifact,
    HostedToolCall,
    LLMPort,
)
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.runtime.db.models.threads import generate_thread_message_id
from app.kernel.runtime.responses.interaction import (
    InteractionProtocolAdapter,
    InteractionProtocolEvent,
)
from app.kernel.runtime.responses.schemas import ResponseCreateRequest
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.tool_calls import (
    RuntimeToolExecutionService,
    ToolExecutionCommand,
    summarize_parameters,
    summarize_tool_payload,
)
from app.kernel.runtime.threads.service import ThreadService

logger = logging.getLogger(__name__)

_PUBLIC_EXECUTION_ERROR = "Response execution failed"


class ThreadProjectionWriter:
    """Project response execution into runtime thread messages."""

    def __init__(self, thread_service: ThreadService | None) -> None:
        self.thread_service = thread_service

    @staticmethod
    def attachment_context(metadata: Any) -> str:
        contexts = metadata.get("_attachment_context") if isinstance(metadata, dict) else None
        if not isinstance(contexts, list):
            return ""
        blocks: list[str] = []
        for index, context in enumerate(contexts, start=1):
            if not isinstance(context, dict):
                continue
            name = context.get("name") or f"attachment-{index}"
            text = context.get("text")
            if isinstance(text, str) and text.strip():
                blocks.append(f"[{name}]\n{text}")
        if not blocks:
            return ""
        return "Attached context:\n" + "\n\n".join(blocks)

    @staticmethod
    def with_attachment_context(content: str, metadata: Any) -> str:
        attachment_context = ThreadProjectionWriter.attachment_context(metadata)
        if not attachment_context:
            return content
        return f"{content}\n\n{attachment_context}" if content else attachment_context

    def touch_latest_run(self, response) -> None:
        if not self.thread_service or not response.thread_id or not response.run_id:
            return
        try:
            self.thread_service.update_thread(
                thread_id=response.thread_id,
                latest_run_id=response.run_id,
            )
        except Exception:
            return

    def store_input(
        self,
        response,
        messages: list[ChatMessage],
        message_metadata: list[dict[str, Any]] | None = None,
    ) -> str | None:
        if not self.thread_service or not response.thread_id:
            return None
        thread_messages = self.thread_service.thread_repo.list_messages(response.thread_id)
        parent_message_id = thread_messages[-1].id if thread_messages else None
        last_appended_message_id = parent_message_id
        metadata_index = 0
        for message in messages:
            if message.role not in {"user", "assistant"}:
                continue
            metadata = (
                message_metadata[metadata_index]
                if message_metadata and metadata_index < len(message_metadata)
                else {}
            ) or {}
            persisted_metadata = {
                key: value for key, value in metadata.items() if not key.startswith("_")
            }
            metadata_index += 1
            agui_message_id = metadata.get("agui_message_id")
            if message.role == "user" and isinstance(agui_message_id, str):
                existing = self.thread_service.thread_repo.get_message(
                    response.thread_id,
                    agui_message_id,
                )
                if existing is None:
                    existing = next(
                        (
                            item
                            for item in self.thread_service.thread_repo.list_messages(
                                response.thread_id
                            )
                            if (item.metadata_json or {}).get("agui_message_id")
                            == agui_message_id
                        ),
                        None,
                    )
                if existing is not None:
                    if existing.role != "user":
                        raise ValidationError("AG-UI message reuse requires an existing user message")
                    parent_message_id = existing.id
                    last_appended_message_id = existing.id
                    continue
            if "parent_message_id" in metadata:
                candidate_parent = metadata.get("parent_message_id")
                parent_message_id = candidate_parent if isinstance(candidate_parent, str) else None
            stored_message = self.thread_service.append_message(
                thread_id=response.thread_id,
                role=message.role,
                content=message.content,
                run_id=response.run_id,
                response_id=response.id,
                parent_message_id=parent_message_id,
                message_type="text",
                attachments_json=(
                    persisted_metadata.get("attachments")
                    if isinstance(persisted_metadata.get("attachments"), list)
                    else None
                ),
                citations_json=(
                    persisted_metadata.get("citations")
                    if isinstance(persisted_metadata.get("citations"), list)
                    else None
                ),
                metadata={"response_id": response.id, **persisted_metadata},
            )
            parent_message_id = stored_message.id
            last_appended_message_id = stored_message.id
        return last_appended_message_id

    def store_failure(self, response, *, parent_message_id: str | None) -> None:
        if not self.thread_service or not response.thread_id:
            return
        self.thread_service.append_message(
            thread_id=response.thread_id,
            role="assistant",
            content=response.error_message or "Response failed",
            run_id=response.run_id,
            response_id=response.id,
            parent_message_id=parent_message_id,
            message_type="error",
            status="failed",
            error_code=response.error_code,
            error_message=response.error_message,
            metadata={
                "response_id": response.id,
                "run_id": response.run_id,
                "error_code": response.error_code,
                "error_message": response.error_message,
            },
        )

    def store_output(
        self,
        response,
        *,
        content: str,
        parent_message_id: str | None,
        message_id: str | None = None,
        reasoning: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        if not self.thread_service or not response.thread_id:
            return
        self.thread_service.append_message(
            thread_id=response.thread_id,
            message_id=message_id or generate_thread_message_id(),
            role="assistant",
            content=content,
            run_id=response.run_id,
            response_id=response.id,
            parent_message_id=parent_message_id,
            message_type="text",
            status="completed",
            citations_json=citations,
            tool_calls_json=tool_calls,
            metadata={
                "response_id": response.id,
                "run_id": response.run_id,
                "branch_id": (response.metadata_json or {}).get("branch_id"),
                **({"reasoning": reasoning} if reasoning else {}),
                **({"citations": citations} if citations else {}),
                **({"artifacts": artifacts} if artifacts else {}),
                **({"tool_calls": tool_calls} if tool_calls else {}),
            },
        )


class ResponseExecutionService:
    """Execute response model calls and format completion payloads."""

    def __init__(self, llm_port: LLMPort) -> None:
        self.llm_port = llm_port

    def build_completion_output(
        self,
        text: str,
        finish_reason: str | None,
        reasoning: str | None = None,
    ) -> dict[str, Any]:
        output = {
            "text": text,
            "items": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": text,
                        }
                    ],
                }
            ],
            "finish_reason": finish_reason,
        }
        if reasoning:
            output["reasoning"] = reasoning
        return output

    def build_usage(self, prompt_tokens: int, completion_tokens: int) -> dict[str, Any]:
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    async def execute_chat(self, *, response, messages: list[ChatMessage]):
        reasoning_effort = (response.metadata_json or {}).get("reasoning_effort")
        hosted_tools = list((response.input_json or {}).get("tools") or [])
        return await self.llm_port.chat(
            messages=messages,
            model=response.model or "model:openai:gpt-5.1",
            run_id=response.run_id,
            hosted_tools=hosted_tools,
            reasoning_effort=(
                reasoning_effort
                if isinstance(reasoning_effort, str) and reasoning_effort
                else None
            ),
        )

    def stream_chat(self, *, response, messages: list[ChatMessage]):
        reasoning_effort = (response.metadata_json or {}).get("reasoning_effort")
        hosted_tools = list((response.input_json or {}).get("tools") or [])
        return self.llm_port.stream_chat(
            messages=messages,
            model=response.model or "model:openai:gpt-5.1",
            run_id=response.run_id,
            hosted_tools=hosted_tools,
            reasoning_effort=(
                reasoning_effort
                if isinstance(reasoning_effort, str) and reasoning_effort
                else None
            ),
        )


class ResponseProjectionCoordinator:
    """Coordinate response resources and semantic events around run execution."""

    _TEXT_FLUSH_INTERVAL_SECONDS = 0.05
    _TEXT_FLUSH_BYTES = 1024

    def __init__(
        self,
        *,
        response_service: ResponseService,
        llm_port: LLMPort,
        thread_service: ThreadService | None = None,
        storage_port: StoragePort | None = None,
    ) -> None:
        self.response_service = response_service
        self.llm_port = llm_port
        self.thread_service = thread_service
        self.storage_port = storage_port
        self.execution_service = ResponseExecutionService(llm_port)
        self.thread_writer = ThreadProjectionWriter(thread_service)

    @staticmethod
    def _attachment_context(metadata: Any) -> str:
        return ThreadProjectionWriter.attachment_context(metadata)

    @staticmethod
    def _with_attachment_context(content: str, metadata: Any) -> str:
        return ThreadProjectionWriter.with_attachment_context(content, metadata)

    @staticmethod
    def _coerce_input_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            messages = value.get("messages")
            if isinstance(messages, list):
                lines = []
                for item in messages:
                    if isinstance(item, dict):
                        content = item.get("content")
                        if content:
                            lines.append(
                                ResponseProjectionCoordinator._with_attachment_context(
                                    str(content),
                                    item.get("metadata"),
                                )
                            )
                return "\n".join(lines)
            items = value.get("items")
            if isinstance(items, list):
                lines = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "input_text" and item.get("text"):
                        lines.append(str(item["text"]))
                        continue
                    if item.get("content"):
                        lines.append(str(item["content"]))
                return "\n".join(lines)
        if isinstance(value, list):
            lines = []
            for item in value:
                if isinstance(item, dict) and item.get("content"):
                    lines.append(str(item["content"]))
                elif item:
                    lines.append(str(item))
            return "\n".join(lines)
        return str(value)

    def _build_messages(self, payload: ResponseCreateRequest) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        if payload.instructions:
            messages.append(ChatMessage(role="system", content=payload.instructions))
        text = self._coerce_input_text(payload.input)
        if text:
            messages.append(ChatMessage(role="user", content=text))
        return messages

    def _build_runtime_messages(
        self,
        payload: ResponseCreateRequest,
        *,
        head_message_id: str | None,
    ) -> list[ChatMessage]:
        if (
            not self.thread_service
            or not payload.thread_id
            or not head_message_id
        ):
            return self._build_messages(payload)
        messages: list[ChatMessage] = []
        if payload.instructions:
            messages.append(ChatMessage(role="system", content=payload.instructions))
        for message in self.thread_service.thread_repo.message_lineage(
            payload.thread_id,
            head_message_id,
        ):
            if message.status != "completed" or message.role not in {
                "user",
                "assistant",
                "tool",
            }:
                continue
            if message.content:
                messages.append(ChatMessage(role=message.role, content=message.content))
        return messages

    @staticmethod
    def _extract_input_message_metadata(payload: ResponseCreateRequest) -> list[dict[str, Any]]:
        if not isinstance(payload.input, dict):
            return []
        raw_messages = payload.input.get("messages")
        if not isinstance(raw_messages, list):
            return []
        extracted: list[dict[str, Any]] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                extracted.append({})
                continue
            metadata = item.get("metadata")
            extracted.append(metadata if isinstance(metadata, dict) else {})
        return extracted

    def _touch_thread_latest_run(self, response) -> None:
        self.thread_writer.touch_latest_run(response)

    def _store_thread_input(
        self,
        response,
        messages: list[ChatMessage],
        message_metadata: list[dict[str, Any]] | None = None,
    ) -> str | None:
        return self.thread_writer.store_input(response, messages, message_metadata)

    def _store_thread_failure(self, response, *, parent_message_id: str | None) -> None:
        self.thread_writer.store_failure(response, parent_message_id=parent_message_id)

    def _build_completion_output(
        self,
        text: str,
        finish_reason: str | None,
        reasoning: str | None = None,
    ) -> dict[str, Any]:
        return self.execution_service.build_completion_output(text, finish_reason, reasoning)

    def _build_usage(self, prompt_tokens: int, completion_tokens: int) -> dict[str, Any]:
        return self.execution_service.build_usage(prompt_tokens, completion_tokens)

    async def _record_hosted_tool_calls(
        self,
        response,
        calls: list[HostedToolCall],
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        if not response.run_id or not calls:
            return [], {}
        execution = RuntimeToolExecutionService(
            db=self.response_service.db,
            ctx=self.response_service.ctx,
            trace_writer=self.response_service.trace_writer,
            lease_owner=f"response:{response.id}",
            storage_port=self.storage_port,
        )
        projected: list[dict[str, Any]] = []
        step_ids: dict[str, str] = {}
        for index, call in enumerate(calls, start=1):
            tool_call_id = call.id or f"hosted_{index}"
            command = ToolExecutionCommand(
                run_id=response.run_id,
                tool_call_id=tool_call_id,
                tool_ref=call.name,
                arguments=call.arguments,
                idempotency_key=f"hosted:{response.run_id}:{tool_call_id}",
            )
            claim = execution.claim(command)
            self.response_service.trace_writer.update_step_status(
                claim.run_step.id,
                claim.run_step.status,
                metrics={
                    "tool_call": {
                        "tool_call_id": tool_call_id,
                        "tool_ref": call.name,
                        "tool_name": call.name,
                        "tool_type": "hosted",
                        "arguments": summarize_parameters(call.arguments),
                        "metadata": {"provider": "openai", "hosted": True},
                    }
                },
            )
            execution.mark_running(claim.record.id)
            succeeded = call.status.lower() in {"completed", "succeeded"}
            record = await execution.complete(
                claim.record.id,
                ToolResponse(
                    result=call.result,
                    success=succeeded,
                    error=None if succeeded else "Hosted tool execution failed",
                    metadata={
                        "provider": "openai",
                        "hosted": True,
                        "tool_type": "hosted",
                    },
                ),
            )
            step_ids[call.name] = claim.run_step.id
            projected.append(
                {
                    "id": record.id,
                    "run_step_tool_call_id": record.id,
                    "run_step_id": record.run_step_id,
                    "tool_call_id": tool_call_id,
                    "name": call.name,
                    "tool_name": call.name,
                    "tool_type": "hosted",
                    "status": "completed" if succeeded else "failed",
                    "arguments_json": summarize_parameters(call.arguments),
                    "result_json": summarize_tool_payload(call.result),
                    "metadata_json": {
                        "provider": "openai",
                        "hosted": True,
                    },
                }
            )
        return projected, step_ids

    @staticmethod
    def _safe_artifact_segment(value: str, fallback: str) -> str:
        normalized = value.replace("\\", "/").rsplit("/", 1)[-1]
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._")
        return normalized or fallback

    async def _persist_hosted_artifacts(
        self,
        response,
        artifacts: list[HostedArtifact],
        step_ids: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not artifacts:
            return []
        if not response.run_id or self.storage_port is None:
            raise ValidationError("Governed storage is required for hosted tool files")
        projected: list[dict[str, Any]] = []
        for artifact in artifacts:
            container = self._safe_artifact_segment(
                artifact.container_id,
                "container",
            )
            file_id = self._safe_artifact_segment(artifact.file_id, "file")
            filename = self._safe_artifact_segment(artifact.filename, file_id)
            storage_key = (
                f"tenants/{self.response_service.ctx.tenant_id}/"
                f"workspaces/{self.response_service.ctx.workspace_id}/"
                f"runs/{response.run_id}/hosted/{container}/{file_id}/{filename}"
            )
            await self.storage_port.put(
                storage_key,
                artifact.content,
                content_type=artifact.mime,
                metadata={
                    "provider": "openai",
                    "container_id": artifact.container_id,
                    "file_id": artifact.file_id,
                },
            )
            stored = self.response_service.trace_writer.create_artifact(
                run_id=response.run_id,
                step_id=step_ids.get("openai.code_interpreter"),
                artifact_type="file",
                storage_key=storage_key,
                mime=artifact.mime or "application/octet-stream",
                size_bytes=len(artifact.content),
                sha256=hashlib.sha256(artifact.content).hexdigest(),
                meta={
                    "kind": "hosted_tool_file",
                    "provider": "openai",
                    "name": filename,
                    "filename": filename,
                    "container_id": artifact.container_id,
                    "file_id": artifact.file_id,
                },
            )
            projected.append(
                {
                    "id": stored.id,
                    "type": stored.type,
                    "name": filename,
                    "mime": stored.mime,
                    "size_bytes": stored.size_bytes,
                    "sha256": stored.sha256,
                    "download_url": (
                        f"/api/v1/runs/{response.run_id}/artifacts/"
                        f"{stored.id}/content"
                    ),
                }
            )
        return projected

    @staticmethod
    def _hosted_tool_events(
        protocol: InteractionProtocolAdapter,
        calls: list[HostedToolCall],
        records: list[dict[str, Any]],
        assistant_message_id: str,
    ) -> list[InteractionProtocolEvent]:
        events: list[InteractionProtocolEvent] = []
        record_by_call = {str(item["tool_call_id"]): item for item in records}
        for index, call in enumerate(calls, start=1):
            tool_call_id = call.id or f"hosted_{index}"
            record = record_by_call.get(tool_call_id, {})
            events.extend(
                [
                    protocol.tool_started(
                        tool_call_id=tool_call_id,
                        tool_name=call.name,
                        parent_message_id=assistant_message_id,
                    ),
                    protocol.tool_arguments(
                        tool_call_id=tool_call_id,
                        delta=json.dumps(
                            record.get("arguments_json")
                            or summarize_parameters(call.arguments),
                            ensure_ascii=False,
                        ),
                    ),
                    protocol.tool_ended(tool_call_id=tool_call_id),
                    protocol.tool_result(
                        message_id=f"{assistant_message_id}_{tool_call_id}_result",
                        tool_call_id=tool_call_id,
                        content=json.dumps(
                            record.get("result_json")
                            or summarize_tool_payload(call.result),
                            ensure_ascii=False,
                        ),
                    ),
                    protocol.custom(
                        "soit.tool_status",
                        {
                            "schemaVersion": 1,
                            "toolCallId": tool_call_id,
                            "toolName": call.name,
                            "toolType": "hosted",
                            "status": record.get("status", call.status),
                            "runStepId": record.get("run_step_id"),
                            "runStepToolCallId": record.get(
                                "run_step_tool_call_id"
                            ),
                            "metadata": {"provider": "openai", "hosted": True},
                        },
                    ),
                ]
            )
        return events

    def _persist_interaction_event(
        self,
        *,
        response,
        protocol: InteractionProtocolAdapter,
        event: InteractionProtocolEvent,
    ) -> dict[str, Any]:
        stored = self.response_service.append_event(
            response=response,
            event_type=event.type,
            payload=event.payload,
            source=protocol.source,
            protocol_version=protocol.protocol_version,
            interaction_id=str(response.metadata_json.get("interaction_id") or "") or None,
        )
        self.response_service.publish_persisted_event(stored)
        return {
            "id": f"{response.id}:{stored.sequence}",
            "data": stored.payload_json,
        }

    def validate_interaction_request(
        self,
        payload: ResponseCreateRequest,
        interaction_id: str,
    ) -> None:
        """Validate protocol invariants before an SSE response is started."""

        if not payload.thread_id:
            raise ValidationError("A protocol interaction requires a thread")
        request_hash = str(payload.metadata.get("request_hash") or "")
        if not request_hash:
            raise ValidationError("A protocol interaction requires a request hash")
        existing_interaction = self.response_service.get_interaction(interaction_id)
        if existing_interaction and existing_interaction.request_hash != request_hash:
            raise ConflictError("Interaction ID was already used with a different request")

    async def execute_interaction_stream(
        self,
        payload: ResponseCreateRequest,
        *,
        interaction_id: str,
        parent_interaction_id: str | None,
        protocol: InteractionProtocolAdapter,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute a response and persist a protocol-native event stream."""

        self.validate_interaction_request(payload, interaction_id)
        request_hash = str(payload.metadata.get("request_hash") or "")
        existing_interaction = self.response_service.get_interaction(interaction_id)
        if existing_interaction and existing_interaction.response_id:
            stored_events = self.response_service.list_response_events(
                existing_interaction.response_id,
                limit=10_000,
                offset=0,
            )
            for event in stored_events:
                yield {
                    "id": f"{event.response_id}:{event.sequence}",
                    "data": event.payload_json,
                }
            return

        response = self.response_service.create_response(payload, emit_initial_events=False)
        self.response_service.create_interaction(
            interaction_id=interaction_id,
            parent_interaction_id=parent_interaction_id,
            response=response,
            request_hash=request_hash,
        )
        response = self.response_service.mark_running(response)
        if response.run_id:
            self.response_service.trace_writer.update_run_status(response.run_id, "running")
        self._touch_thread_latest_run(response)

        input_messages = self._build_messages(payload)
        assistant_parent_message_id = self._store_thread_input(
            response,
            input_messages,
            self._extract_input_message_metadata(payload),
        )
        messages = self._build_runtime_messages(
            payload,
            head_message_id=assistant_parent_message_id,
        )
        assistant_message_id = generate_thread_message_id()

        def persist(event: InteractionProtocolEvent) -> dict[str, Any]:
            return self._persist_interaction_event(
                response=response,
                protocol=protocol,
                event=event,
            )

        yield persist(
            protocol.run_started(
                thread_id=payload.thread_id,
                interaction_id=interaction_id,
                parent_interaction_id=parent_interaction_id,
            )
        )
        yield persist(protocol.resources(response=response, interaction_id=interaction_id))

        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        model_used = response.model or "model:openai:gpt-5.1"
        finish_reason: str | None = None
        show_reasoning = bool((response.metadata_json or {}).get("show_reasoning"))
        reasoning_message_id = f"{assistant_message_id}_reasoning"
        reasoning_started = False
        reasoning_ended = False
        text_started = False
        hosted_tool_calls: list[HostedToolCall] = []
        citations: list[dict[str, Any]] = []
        hosted_artifacts: list[HostedArtifact] = []

        def interaction_was_canceled() -> bool:
            current = self.response_service.get_response(response.id)
            if current.status != "canceled":
                return False
            self.response_service.update_interaction_status(interaction_id, "canceled")
            return True

        try:
            stream: AsyncIterator[ChatStreamChunk] | None
            try:
                stream = self.execution_service.stream_chat(response=response, messages=messages)
            except NotImplementedError:
                stream = None

            if stream is None:
                result = await self.execution_service.execute_chat(response=response, messages=messages)
                if interaction_was_canceled():
                    return
                delta = result.text or ""
                text_parts.append(delta)
                prompt_tokens = result.tokens_prompt
                completion_tokens = result.tokens_completion
                model_used = result.model or model_used
                finish_reason = result.finish_reason
                hosted_tool_calls.extend(result.hosted_tool_calls)
                citations.extend(result.citations)
                hosted_artifacts.extend(result.hosted_artifacts)
                if show_reasoning and result.reasoning:
                    reasoning_started = True
                    reasoning_parts.append(result.reasoning)
                    for reasoning_event in protocol.reasoning_started(
                        message_id=reasoning_message_id
                    ):
                        yield persist(reasoning_event)
                    yield persist(
                        protocol.reasoning_content(
                            message_id=reasoning_message_id,
                            delta=result.reasoning,
                        )
                    )
                    for reasoning_event in protocol.reasoning_ended(
                        message_id=reasoning_message_id
                    ):
                        yield persist(reasoning_event)
                    reasoning_ended = True
                yield persist(protocol.text_started(message_id=assistant_message_id))
                text_started = True
                if delta:
                    yield persist(protocol.text_content(message_id=assistant_message_id, delta=delta))
            else:
                delta_parts: list[str] = []
                delta_bytes = 0
                last_delta_flush = time.monotonic()
                async for chunk in stream:
                    if interaction_was_canceled():
                        return
                    if show_reasoning and chunk.reasoning_delta and not reasoning_ended:
                        if not reasoning_started:
                            for reasoning_event in protocol.reasoning_started(
                                message_id=reasoning_message_id
                            ):
                                yield persist(reasoning_event)
                            reasoning_started = True
                        reasoning_parts.append(chunk.reasoning_delta)
                        yield persist(
                            protocol.reasoning_content(
                                message_id=reasoning_message_id,
                                delta=chunk.reasoning_delta,
                            )
                        )
                    if chunk.delta:
                        if reasoning_started and not reasoning_ended:
                            for reasoning_event in protocol.reasoning_ended(
                                message_id=reasoning_message_id
                            ):
                                yield persist(reasoning_event)
                            reasoning_ended = True
                        if not text_started:
                            yield persist(protocol.text_started(message_id=assistant_message_id))
                            text_started = True
                        text_parts.append(chunk.delta)
                        delta_parts.append(chunk.delta)
                        delta_bytes += len(chunk.delta.encode("utf-8"))
                        now = time.monotonic()
                        if (
                            delta_bytes >= self._TEXT_FLUSH_BYTES
                            or now - last_delta_flush >= self._TEXT_FLUSH_INTERVAL_SECONDS
                        ):
                            yield persist(
                                protocol.text_content(
                                    message_id=assistant_message_id,
                                    delta="".join(delta_parts),
                                )
                            )
                            delta_parts = []
                            delta_bytes = 0
                            last_delta_flush = now
                    if chunk.tokens_prompt:
                        prompt_tokens = chunk.tokens_prompt
                    if chunk.tokens_completion:
                        completion_tokens = chunk.tokens_completion
                    if chunk.model:
                        model_used = chunk.model
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason
                    if chunk.hosted_tool_calls:
                        hosted_tool_calls.extend(chunk.hosted_tool_calls)
                    if chunk.citations:
                        citations.extend(chunk.citations)
                    if chunk.hosted_artifacts:
                        hosted_artifacts.extend(chunk.hosted_artifacts)
                if delta_parts:
                    yield persist(
                        protocol.text_content(
                            message_id=assistant_message_id,
                            delta="".join(delta_parts),
                        )
                    )

            if reasoning_started and not reasoning_ended:
                for reasoning_event in protocol.reasoning_ended(
                    message_id=reasoning_message_id
                ):
                    yield persist(reasoning_event)
                reasoning_ended = True
            if not text_started:
                yield persist(protocol.text_started(message_id=assistant_message_id))
                text_started = True

            if interaction_was_canceled():
                return

            output_text = "".join(text_parts)
            reasoning_text = "".join(reasoning_parts) or None
            usage_payload = self._build_usage(prompt_tokens, completion_tokens)
            hosted_tool_records, hosted_step_ids = await self._record_hosted_tool_calls(
                response,
                hosted_tool_calls,
            )
            governed_artifacts = await self._persist_hosted_artifacts(
                response,
                hosted_artifacts,
                hosted_step_ids,
            )
            for tool_event in self._hosted_tool_events(
                protocol,
                hosted_tool_calls,
                hosted_tool_records,
                assistant_message_id,
            ):
                yield persist(tool_event)
            for citation in citations:
                yield persist(
                    protocol.custom(
                        "soit.source",
                        {"schemaVersion": 1, **citation},
                    )
                )
            for artifact in governed_artifacts:
                yield persist(
                    protocol.custom(
                        "soit.artifact",
                        {"schemaVersion": 1, **artifact},
                    )
                )
            self.thread_writer.store_output(
                response,
                message_id=assistant_message_id,
                content=output_text,
                parent_message_id=assistant_parent_message_id,
                reasoning=reasoning_text,
                citations=citations,
                artifacts=governed_artifacts,
                tool_calls=hosted_tool_records,
            )
            completion_output = self._build_completion_output(
                output_text,
                finish_reason,
                reasoning_text,
            )
            if citations:
                completion_output["citations"] = citations
            if governed_artifacts:
                completion_output["artifacts"] = governed_artifacts
            if hosted_tool_records:
                completion_output["hosted_tool_calls"] = hosted_tool_records
            response = self.response_service.complete_response(
                response=response,
                output_json=completion_output,
                usage_json=usage_payload,
                output_event_type=None,
                completed_event_type=None,
            )
            yield persist(protocol.text_ended(message_id=assistant_message_id))
            yield persist(protocol.usage(usage=usage_payload, model=model_used))
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "succeeded",
                    output_summary=output_text,
                )
            self.response_service.update_interaction_status(interaction_id, "succeeded")
            yield persist(
                protocol.run_finished(
                    thread_id=payload.thread_id,
                    interaction_id=interaction_id,
                    result={
                        "status": response.status,
                        "responseId": response.id,
                        "executionRunId": response.run_id,
                        "finishReason": finish_reason,
                    },
                )
            )
        except Exception as exc:
            if interaction_was_canceled():
                return
            logger.exception("Response interaction execution failed", exc_info=exc)
            if response.status in {"succeeded", "failed", "canceled"}:
                raise
            response = self.response_service.fail_response(
                response=response,
                error_code="response_execution_failed",
                error_message=_PUBLIC_EXECUTION_ERROR,
                source=protocol.source,
                failed_event_type=None,
            )
            self._store_thread_failure(response, parent_message_id=assistant_parent_message_id)
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "failed",
                    output_summary=response.error_message,
                    error_code=response.error_code,
                    error_message=response.error_message,
                )
            self.response_service.update_interaction_status(interaction_id, "failed")
            yield persist(
                protocol.run_error(
                    code=response.error_code or "response_execution_failed",
                    message=response.error_message or _PUBLIC_EXECUTION_ERROR,
                )
            )

    async def execute(self, payload: ResponseCreateRequest):
        response = self.response_service.create_response(payload)
        response = self.response_service.mark_running(response)
        if response.run_id:
            self.response_service.trace_writer.update_run_status(response.run_id, "running")
        self._touch_thread_latest_run(response)

        input_messages = self._build_messages(payload)
        assistant_parent_message_id = self._store_thread_input(
            response,
            input_messages,
            self._extract_input_message_metadata(payload),
        )
        messages = self._build_runtime_messages(
            payload,
            head_message_id=assistant_parent_message_id,
        )

        try:
            result = await self.execution_service.execute_chat(response=response, messages=messages)
            output_text = result.text or ""
            reasoning_text = (
                result.reasoning
                if bool((response.metadata_json or {}).get("show_reasoning"))
                else None
            )
            output_payload = self._build_completion_output(
                output_text,
                result.finish_reason,
                reasoning_text,
            )
            usage_payload = self._build_usage(result.tokens_prompt, result.tokens_completion)
            self.thread_writer.store_output(
                response,
                content=output_text,
                parent_message_id=assistant_parent_message_id,
                reasoning=reasoning_text,
            )
            response = self.response_service.complete_response(
                response=response,
                output_json=output_payload,
                usage_json=usage_payload,
                output_event_payload={"text": output_text},
                completed_event_payload={
                    "usage": usage_payload,
                    "finish_reason": result.finish_reason,
                    "model": result.model or response.model,
                },
            )
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "succeeded",
                    output_summary=output_text,
                )
            return response
        except Exception as exc:
            logger.exception("Response execution failed", exc_info=exc)
            if response.status in {"succeeded", "failed", "canceled"}:
                raise
            response = self.response_service.fail_response(
                response=response,
                error_code="response_execution_failed",
                error_message=_PUBLIC_EXECUTION_ERROR,
            )
            self._store_thread_failure(response, parent_message_id=assistant_parent_message_id)
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "failed",
                    output_summary=response.error_message,
                    error_code=response.error_code,
                    error_message=response.error_message,
                )
            raise

