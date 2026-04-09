"""Response resource coordinator for semantic API flows."""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.kernel.ports.llm.interface import ChatMessage, LLMPort, ChatStreamChunk
from app.kernel.responses.schemas import ResponseCreateRequest
from app.kernel.responses.service import ResponseService
from app.kernel.runtime.core.service import RuntimeCoreService


class ResponseProjectionCoordinator:
    """Coordinate response resources and semantic events around run execution."""

    def __init__(
        self,
        *,
        response_service: ResponseService,
        llm_port: LLMPort,
        runtime_core: RuntimeCoreService | None = None,
    ) -> None:
        self.response_service = response_service
        self.llm_port = llm_port
        self.runtime_core = runtime_core

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
                            lines.append(str(content))
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
        if not self.runtime_core or not response.thread_id or not response.run_id:
            return
        try:
            self.runtime_core.update_thread(
                thread_id=response.thread_id,
                latest_run_id=response.run_id,
            )
        except Exception:
            return

    def _store_thread_input(
        self,
        response,
        messages: list[ChatMessage],
        message_metadata: list[dict[str, Any]] | None = None,
    ) -> str | None:
        if not self.runtime_core or not response.thread_id:
            return None
        thread_messages = self.runtime_core.thread_repo.list_messages(response.thread_id)
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
            metadata_index += 1
            stored_message = self.runtime_core.append_message(
                thread_id=response.thread_id,
                role=message.role,
                content=message.content,
                run_id=response.run_id,
                response_id=response.id,
                parent_message_id=parent_message_id,
                message_type="text",
                attachments_json=metadata.get("attachments") if isinstance(metadata.get("attachments"), list) else None,
                citations_json=metadata.get("citations") if isinstance(metadata.get("citations"), list) else None,
                metadata={"response_id": response.id, **metadata},
            )
            parent_message_id = stored_message.id
            last_appended_message_id = stored_message.id
        return last_appended_message_id

    def _build_completion_output(self, text: str, finish_reason: str | None) -> dict[str, Any]:
        return {
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

    def _build_usage(self, prompt_tokens: int, completion_tokens: int) -> dict[str, Any]:
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

    async def execute(self, payload: ResponseCreateRequest):
        response = self.response_service.create_response(payload)
        response = self.response_service.mark_in_progress(response)
        if response.run_id:
            self.response_service.trace_writer.update_run_status(response.run_id, "running")
        self._touch_thread_latest_run(response)

        messages = self._build_messages(payload)
        assistant_parent_message_id = self._store_thread_input(
            response,
            messages,
            self._extract_input_message_metadata(payload),
        )

        try:
            result = await self.llm_port.chat(
                messages=messages,
                model=response.model or "model:openai:gpt-5.1",
                run_id=response.run_id,
            )
            output_text = result.text or ""
            output_payload = self._build_completion_output(output_text, result.finish_reason)
            usage_payload = self._build_usage(result.tokens_prompt, result.tokens_completion)
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
            if self.runtime_core and response.thread_id:
                self.runtime_core.append_message(
                    thread_id=response.thread_id,
                    role="assistant",
                    content=output_text,
                    run_id=response.run_id,
                    response_id=response.id,
                    parent_message_id=assistant_parent_message_id,
                    message_type="text",
                    status="completed",
                    metadata={"response_id": response.id, "run_id": response.run_id},
                )
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "succeeded",
                    output_summary=output_text,
                )
            return response
        except Exception as exc:
            response = self.response_service.fail_response(
                response=response,
                error_code="response_execution_failed",
                error_message=str(exc),
            )
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "failed",
                    output_summary=response.error_message,
                    error_code=response.error_code,
                    error_message=response.error_message,
                )
            raise

    async def execute_stream(self, payload: ResponseCreateRequest) -> AsyncIterator[dict[str, Any]]:
        response = self.response_service.create_response(payload)
        created_events = self.response_service.list_response_events(response.id, limit=10, offset=0)
        response = self.response_service.mark_in_progress(response)
        if response.run_id:
            self.response_service.trace_writer.update_run_status(response.run_id, "running")
        self._touch_thread_latest_run(response)

        messages = self._build_messages(payload)
        assistant_parent_message_id = self._store_thread_input(
            response,
            messages,
            self._extract_input_message_metadata(payload),
        )

        for event in created_events:
            yield {
                "event": event.type,
                "data": event.payload_json,
            }

        text_parts: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        model_used = response.model or "model:openai:gpt-5.1"
        finish_reason: str | None = None

        try:
            stream: AsyncIterator[ChatStreamChunk] | None = None
            try:
                stream = self.llm_port.stream_chat(
                    messages=messages,
                    model=response.model or "model:openai:gpt-5.1",
                    run_id=response.run_id,
                )
            except NotImplementedError:
                stream = None

            if stream is None:
                result = await self.llm_port.chat(
                    messages=messages,
                    model=response.model or "model:openai:gpt-5.1",
                    run_id=response.run_id,
                )
                text_parts.append(result.text or "")
                prompt_tokens = result.tokens_prompt
                completion_tokens = result.tokens_completion
                model_used = result.model or model_used
                finish_reason = result.finish_reason
                delta_event = self.response_service.append_event(
                    response=response,
                    event_type="response.output_text.delta",
                    payload={"delta": result.text or ""},
                )
                yield {"event": delta_event.type, "data": delta_event.payload_json}
            else:
                async for chunk in stream:
                    if chunk.delta:
                        text_parts.append(chunk.delta)
                        delta_event = self.response_service.append_event(
                            response=response,
                            event_type="response.output_text.delta",
                            payload={"delta": chunk.delta},
                        )
                        yield {"event": delta_event.type, "data": delta_event.payload_json}
                    if chunk.tokens_prompt:
                        prompt_tokens = chunk.tokens_prompt
                    if chunk.tokens_completion:
                        completion_tokens = chunk.tokens_completion
                    if chunk.model:
                        model_used = chunk.model
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason

            output_text = "".join(text_parts)
            output_payload = self._build_completion_output(output_text, finish_reason)
            usage_payload = self._build_usage(prompt_tokens, completion_tokens)
            response = self.response_service.complete_response(
                response=response,
                output_json=output_payload,
                usage_json=usage_payload,
                output_event_payload={"text": output_text},
                completed_event_payload={
                    "usage": usage_payload,
                    "finish_reason": finish_reason,
                    "model": model_used,
                    "response_id": response.id,
                    "run_id": response.run_id,
                },
            )
            if self.runtime_core and response.thread_id:
                self.runtime_core.append_message(
                    thread_id=response.thread_id,
                    role="assistant",
                    content=output_text,
                    run_id=response.run_id,
                    response_id=response.id,
                    parent_message_id=assistant_parent_message_id,
                    message_type="text",
                    status="completed",
                    metadata={"response_id": response.id, "run_id": response.run_id},
                )
            yield {
                "event": "response.output_text.completed",
                "data": {"text": output_text},
            }
            yield {
                "event": "response.completed",
                "data": {
                    "usage": usage_payload,
                    "finish_reason": finish_reason,
                    "model": model_used,
                    "response_id": response.id,
                    "run_id": response.run_id,
                },
            }
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "succeeded",
                    output_summary=output_text,
                )
        except Exception as exc:
            response = self.response_service.fail_response(
                response=response,
                error_code="response_execution_failed",
                error_message=str(exc),
            )
            yield {
                "event": "response.failed",
                "data": {
                    "error_code": response.error_code,
                    "error_message": response.error_message,
                },
            }
            if response.run_id:
                self.response_service.trace_writer.update_run_status(
                    response.run_id,
                    "failed",
                    output_summary=response.error_message,
                    error_code=response.error_code,
                    error_message=response.error_message,
                )
            raise

