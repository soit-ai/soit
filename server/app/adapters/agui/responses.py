"""AG-UI request and event mapping for the Responses API."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from enum import Enum
from typing import Any, Literal

from ag_ui.core import (
    ActivitySnapshotEvent,
    CustomEvent,
    ReasoningEndEvent,
    ReasoningMessageContentEvent,
    ReasoningMessageEndEvent,
    ReasoningMessageStartEvent,
    ReasoningStartEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.kernel.runtime.db.models.responses import Response
from app.kernel.runtime.responses.interaction import InteractionProtocolEvent
from app.kernel.runtime.responses.schemas import ResponseCreateRequest


class SoitForwardedProps(BaseModel):
    """Validated SOIT extension carried in AG-UI forwardedProps."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: Literal["agent", "direct"]
    agent_id: str | None = Field(default=None, alias="agentId")
    model_ref: str | None = Field(default=None, alias="modelRef")
    branch_id: str | None = Field(default=None, alias="branchId")
    parent_message_id: str | None = Field(default=None, alias="parentMessageId")
    attachment_ids: list[str] = Field(default_factory=list, alias="attachmentIds")
    request_id: str | None = Field(default=None, alias="requestId")
    deep_thinking: bool | None = Field(default=None, alias="deepThinking")
    reasoning_effort: str | None = Field(default=None, alias="reasoningEffort")
    web_search: bool = Field(default=False, alias="webSearch")
    code_interpreter: bool = Field(default=False, alias="codeInterpreter")
    provider: str | None = None

    @model_validator(mode="after")
    def validate_mode_fields(self) -> SoitForwardedProps:
        if self.mode == "agent":
            if not self.agent_id:
                raise ValueError("agentId is required in agent mode")
            if self.model_ref:
                raise ValueError("modelRef cannot override a published Agent")
        elif not self.model_ref:
            raise ValueError("modelRef is required in direct mode")
        return self


class AgUiResponseRequestAdapter:
    """Map a public AG-UI run request into the internal response command."""

    @staticmethod
    def _soit_props(run_input: RunAgentInput) -> SoitForwardedProps:
        forwarded = run_input.forwarded_props
        if not isinstance(forwarded, dict) or not isinstance(forwarded.get("soit"), dict):
            raise ValueError("forwardedProps.soit is required")
        return SoitForwardedProps.model_validate(forwarded["soit"])

    @staticmethod
    def _latest_user_message(run_input: RunAgentInput) -> dict[str, Any]:
        for message in reversed(run_input.messages):
            if message.role == "user":
                return message.model_dump(by_alias=True, exclude_none=True)
        raise ValueError("An AG-UI run requires a current user message")

    @classmethod
    def _message_context(cls, run_input: RunAgentInput) -> tuple[dict[str, Any], str | None]:
        current = cls._latest_user_message(run_input)
        parent_message_id: str | None = None
        for index in range(len(run_input.messages) - 1, -1, -1):
            message = run_input.messages[index]
            if message.id != current["id"] or message.role != "user":
                continue
            for previous_index in range(index - 1, -1, -1):
                previous = run_input.messages[previous_index]
                if previous.role in {"assistant", "user"}:
                    parent_message_id = previous.id
                    break
            break
        return current, parent_message_id

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text"))
                for part in content
                if isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            )
        return str(content or "")

    @classmethod
    def _branch_context(
        cls,
        run_input: RunAgentInput,
        props: SoitForwardedProps,
    ) -> tuple[str, str | None]:
        current, inferred_parent = cls._message_context(run_input)
        parent_message_id = props.parent_message_id or inferred_parent
        if props.branch_id:
            return props.branch_id, parent_message_id
        branch_seed = json.dumps(
            {
                "thread_id": run_input.thread_id,
                "parent_message_id": parent_message_id,
                "content": cls._message_text(current),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        branch_id = f"branch_{hashlib.sha256(branch_seed.encode('utf-8')).hexdigest()[:24]}"
        return branch_id, parent_message_id

    def attachment_ids(self, run_input: RunAgentInput) -> list[str]:
        """Return governed attachment references from the SOIT extension."""

        return list(dict.fromkeys(self._soit_props(run_input).attachment_ids))

    @staticmethod
    def _attachment_metadata(
        attachments: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        descriptors: list[dict[str, Any]] = []
        contexts: list[dict[str, str]] = []
        for item in attachments or []:
            descriptor = {key: value for key, value in item.items() if not key.startswith("_")}
            descriptors.append(descriptor)
            context_text = item.get("_context_text")
            if isinstance(context_text, str) and context_text:
                contexts.append(
                    {
                        "id": str(item.get("id") or ""),
                        "name": str(item.get("name") or item.get("filename") or "attachment"),
                        "text": context_text,
                    }
                )
        return descriptors, contexts

    def to_internal(
        self,
        run_input: RunAgentInput,
        *,
        attachments: list[dict[str, Any]] | None = None,
    ) -> ResponseCreateRequest:
        props = self._soit_props(run_input)
        current_message = self._latest_user_message(run_input)
        branch_id, parent_message_id = self._branch_context(run_input, props)
        attachment_descriptors, attachment_context = self._attachment_metadata(attachments)
        current_message["metadata"] = {
            "agui_message_id": current_message["id"],
            "attachment_ids": props.attachment_ids,
            "attachments": attachment_descriptors,
            "_attachment_context": attachment_context,
            "branch_id": branch_id,
            "parent_message_id": parent_message_id,
        }
        request_hash = hashlib.sha256(
            json.dumps(
                run_input.model_dump(by_alias=True, exclude_none=True),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return ResponseCreateRequest(
            model=props.model_ref,
            provider=props.provider,
            thread_id=run_input.thread_id,
            agent_id=props.agent_id,
            input={"messages": [current_message]},
            tools=[
                *([{"type": "web_search"}] if props.web_search else []),
                *(
                    [
                        {
                            "type": "code_interpreter",
                            "container": {"type": "auto", "memory_limit": "4g"},
                        }
                    ]
                    if props.code_interpreter
                    else []
                ),
            ],
            context={"state": run_input.state},
            metadata={
                "protocol": "ag-ui",
                "protocol_version": "0.1.19",
                "interaction_id": run_input.run_id,
                "parent_interaction_id": run_input.parent_run_id,
                "branch_id": branch_id,
                "parent_message_id": parent_message_id,
                "request_id": props.request_id,
                "request_hash": request_hash,
                "deep_thinking": bool(props.deep_thinking),
                "show_reasoning": bool(props.deep_thinking),
                "reasoning_effort": props.reasoning_effort,
            },
        )

    def to_agent_inputs(
        self,
        run_input: RunAgentInput,
        *,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Map the current AG-UI user turn to the published Agent entry contract."""

        props = self._soit_props(run_input)
        current_message = self._latest_user_message(run_input)
        text = self._message_text(current_message)
        branch_id, parent_message_id = self._branch_context(run_input, props)
        attachment_descriptors, attachment_context = self._attachment_metadata(attachments)
        return {
            "input": text,
            "thread_id": run_input.thread_id,
            "request_id": props.request_id or run_input.run_id,
            "_attachments": attachment_descriptors,
            "_attachment_context": attachment_context,
            "_agui_context": {
                "message_id": current_message["id"],
                "parent_message_id": parent_message_id,
                "branch_id": branch_id,
            },
            "_agui_options": {
                "show_reasoning": bool(props.deep_thinking),
                "reasoning_effort": props.reasoning_effort,
            },
            "_agui_resume": [
                item.model_dump(by_alias=True, exclude_none=True)
                for item in (run_input.resume or [])
            ],
        }


class AgUiInteractionProtocolAdapter:
    """Build validated AG-UI events for response interaction streams."""

    source = "ag-ui"
    protocol_version = "ag-ui/0.1.19"

    @staticmethod
    def _event(event: BaseModel) -> InteractionProtocolEvent:
        payload = event.model_dump(by_alias=True, exclude_none=True)
        raw_type = payload["type"]
        event_type = raw_type.value if isinstance(raw_type, Enum) else str(raw_type)
        return InteractionProtocolEvent(type=event_type, payload=payload)

    def run_started(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        parent_interaction_id: str | None,
    ) -> InteractionProtocolEvent:
        return self._event(
            RunStartedEvent(
                thread_id=thread_id,
                run_id=interaction_id,
                parent_run_id=parent_interaction_id,
            )
        )

    def resources(
        self,
        *,
        response: Response,
        interaction_id: str,
    ) -> InteractionProtocolEvent:
        return self._event(
            CustomEvent(
                name="soit.resources",
                value={
                    "schemaVersion": 1,
                    "interactionId": interaction_id,
                    "responseId": response.id,
                    "executionRunId": response.run_id,
                    "taskId": response.task_id,
                    "threadId": response.thread_id,
                    "agentId": response.agent_id,
                },
            )
        )

    def custom(self, name: str, value: dict[str, Any]) -> InteractionProtocolEvent:
        return self._event(CustomEvent(name=name, value=value))

    def activity(
        self,
        *,
        message_id: str,
        activity_type: str,
        content: dict[str, Any],
    ) -> InteractionProtocolEvent:
        return self._event(
            ActivitySnapshotEvent(
                message_id=message_id,
                activity_type=activity_type,
                content=content,
                replace=True,
            )
        )

    def tool_started(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        parent_message_id: str | None,
    ) -> InteractionProtocolEvent:
        return self._event(
            ToolCallStartEvent(
                tool_call_id=tool_call_id,
                tool_call_name=tool_name,
                parent_message_id=parent_message_id,
            )
        )

    def tool_arguments(self, *, tool_call_id: str, delta: str) -> InteractionProtocolEvent:
        return self._event(ToolCallArgsEvent(tool_call_id=tool_call_id, delta=delta))

    def tool_ended(self, *, tool_call_id: str) -> InteractionProtocolEvent:
        return self._event(ToolCallEndEvent(tool_call_id=tool_call_id))

    def tool_result(
        self,
        *,
        message_id: str,
        tool_call_id: str,
        content: str,
    ) -> InteractionProtocolEvent:
        return self._event(
            ToolCallResultEvent(
                message_id=message_id,
                tool_call_id=tool_call_id,
                content=content,
                role="tool",
            )
        )

    def text_started(self, *, message_id: str) -> InteractionProtocolEvent:
        return self._event(TextMessageStartEvent(message_id=message_id, role="assistant"))

    def reasoning_started(
        self,
        *,
        message_id: str,
    ) -> tuple[InteractionProtocolEvent, InteractionProtocolEvent]:
        return (
            self._event(ReasoningStartEvent(message_id=message_id)),
            self._event(
                ReasoningMessageStartEvent(message_id=message_id, role="reasoning")
            ),
        )

    def reasoning_content(
        self,
        *,
        message_id: str,
        delta: str,
    ) -> InteractionProtocolEvent:
        return self._event(ReasoningMessageContentEvent(message_id=message_id, delta=delta))

    def reasoning_ended(
        self,
        *,
        message_id: str,
    ) -> tuple[InteractionProtocolEvent, InteractionProtocolEvent]:
        return (
            self._event(ReasoningMessageEndEvent(message_id=message_id)),
            self._event(ReasoningEndEvent(message_id=message_id)),
        )

    def text_content(self, *, message_id: str, delta: str) -> InteractionProtocolEvent:
        return self._event(TextMessageContentEvent(message_id=message_id, delta=delta))

    def text_ended(self, *, message_id: str) -> InteractionProtocolEvent:
        return self._event(TextMessageEndEvent(message_id=message_id))

    @staticmethod
    def active_text_message_ids(events: Iterable[Any]) -> list[str]:
        """Return text messages that must be closed before an AG-UI terminal."""

        active: dict[str, None] = {}
        for event in events:
            event_type = getattr(event, "type", None)
            payload = getattr(event, "payload_json", None)
            if payload is None:
                payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            message_id = payload.get("messageId")
            if not isinstance(message_id, str) or not message_id:
                continue
            if event_type == "TEXT_MESSAGE_START":
                active[message_id] = None
            elif event_type == "TEXT_MESSAGE_END":
                active.pop(message_id, None)
        return list(active)

    def usage(self, *, usage: dict[str, Any], model: str | None) -> InteractionProtocolEvent:
        return self._event(
            CustomEvent(
                name="soit.usage",
                value={"schemaVersion": 1, "usage": usage, "model": model},
            )
        )

    def run_finished(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        result: dict[str, Any],
    ) -> InteractionProtocolEvent:
        return self._event(
            RunFinishedEvent(
                thread_id=thread_id or "",
                run_id=interaction_id,
                result=result,
            )
        )

    def run_interrupted(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        interrupt: dict[str, Any],
    ) -> InteractionProtocolEvent:
        return self._event(
            RunFinishedEvent(
                thread_id=thread_id,
                run_id=interaction_id,
                outcome={"type": "interrupt", "interrupts": [interrupt]},
            )
        )

    def run_cancelled(
        self,
        *,
        thread_id: str | None,
        interaction_id: str,
    ) -> InteractionProtocolEvent:
        """Represent cancellation as a successful AG-UI protocol termination."""

        return self._event(
            RunFinishedEvent(
                thread_id=thread_id or "",
                run_id=interaction_id,
                result={"status": "canceled", "finishReason": "cancelled"},
            )
        )

    def run_error(self, *, code: str, message: str) -> InteractionProtocolEvent:
        return self._event(RunErrorEvent(code=code, message=message))
