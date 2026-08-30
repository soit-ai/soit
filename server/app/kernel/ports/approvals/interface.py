"""Port for recording that a run stopped and asked a person.

An approval is currently held on the tool call that raised it: the interrupt
travels to the client, the checkpoint is stored on the task, and the decision
comes back through the resume path. That works while somebody is watching the
stream, but it leaves nothing to open afterwards -- a task nobody was watching
shows as waiting with no way to see what it is waiting for, and a decision
already made leaves no record of who made it.

This port writes that record. It is a ledger, not a mechanism: nothing here
decides whether approval is required, and a failure to write must never turn a
run that is waiting into a run that failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.kernel.contracts.context import RequestContext


@dataclass(frozen=True)
class ApprovalRecord:
    """One request for a decision, as the runtime knows it."""

    run_id: str | None
    task_id: str | None
    thread_id: str | None
    agent_id: str | None
    title: str
    policy_ref: str | None
    tool_call_id: str | None
    details: dict[str, Any]


class ApprovalLedgerPort(Protocol):
    """Record approval requests and the decisions that closed them."""

    def record_pending(self, ctx: RequestContext, record: ApprovalRecord) -> str | None:
        """Persist a request for a decision. Returns its id, or None if unwritten.

        Must not raise: the run is already waiting, and losing the record is
        better than turning the wait into a failure.
        """

    def record_decision(
        self,
        ctx: RequestContext,
        *,
        run_id: str | None,
        tool_call_id: str | None,
        approved: bool,
        decided_by: str | None = None,
    ) -> None:
        """Close the pending request for this tool call, if one was written.

        Must not raise, for the same reason: a decision that was acted on is
        not undone by failing to write it down.
        """
