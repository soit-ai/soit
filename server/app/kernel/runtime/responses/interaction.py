"""Protocol-neutral interaction event contracts for response streaming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.kernel.runtime.db.models.responses import Response


@dataclass(frozen=True)
class InteractionProtocolEvent:
    """One protocol event ready for persistence and transport."""

    type: str
    payload: dict[str, Any]


class InteractionProtocolAdapter(Protocol):
    """Build wire events without coupling the runtime kernel to a UI protocol."""

    source: str
    protocol_version: str

    def run_started(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        parent_interaction_id: str | None,
    ) -> InteractionProtocolEvent: ...

    def resources(
        self,
        *,
        response: Response,
        interaction_id: str,
    ) -> InteractionProtocolEvent: ...

    def text_started(self, *, message_id: str) -> InteractionProtocolEvent: ...

    def reasoning_started(
        self,
        *,
        message_id: str,
    ) -> tuple[InteractionProtocolEvent, InteractionProtocolEvent]: ...

    def reasoning_content(
        self,
        *,
        message_id: str,
        delta: str,
    ) -> InteractionProtocolEvent: ...

    def reasoning_ended(
        self,
        *,
        message_id: str,
    ) -> tuple[InteractionProtocolEvent, InteractionProtocolEvent]: ...

    def text_content(self, *, message_id: str, delta: str) -> InteractionProtocolEvent: ...

    def text_ended(self, *, message_id: str) -> InteractionProtocolEvent: ...

    def usage(self, *, usage: dict[str, Any], model: str | None) -> InteractionProtocolEvent: ...

    def run_finished(
        self,
        *,
        thread_id: str,
        interaction_id: str,
        result: dict[str, Any],
    ) -> InteractionProtocolEvent: ...

    def run_error(self, *, code: str, message: str) -> InteractionProtocolEvent: ...
