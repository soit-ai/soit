"""Resume payloads for an agent interaction that stopped for approval.

An agent run that needs a decision stops with its interaction in
``waiting_approval``. It continues when a child interaction carries the
decisions: its agent inputs hold the resolved approval entries under
``_agui_resume`` and the paused run's identifiers under ``_resume_execution``.
The AG-UI transport builds that child from the client's resume request; the
approval consumer builds the same child from the parent's persisted snapshot,
so a decision taken on the approvals page resumes the run without any client
connected.
"""

from __future__ import annotations

from typing import Any

RESUME_ENTRIES_KEY = "_agui_resume"
RESUME_EXECUTION_KEY = "_resume_execution"
AGUI_CONTEXT_KEY = "_agui_context"
ATTACHMENT_IDS_KEY = "_attachment_ids"

APPROVED = "approved"
# A canceled approval is a decision not to run the tool, same as a rejection.
NOT_APPROVED = frozenset({"rejected", "canceled"})


def approval_resume_entry(
    *,
    interrupt_id: str,
    approval_id: str,
    approval_status: str,
) -> dict[str, Any]:
    """One resolved interrupt, in the shape the agent runtime reads."""

    approved = approval_status == APPROVED
    return {
        "interrupt_id": interrupt_id,
        "status": "resolved",
        "payload": {"decision": "approved" if approved else "rejected", "approved": approved},
        "approval_id": approval_id,
        "approval_status": approval_status,
    }


def build_resume_execution_json(
    parent_execution_json: dict[str, Any],
    *,
    entries: list[dict[str, Any]],
    resume_execution: dict[str, str],
    assistant_message_id: str,
) -> dict[str, Any]:
    """Derive the child interaction's job from the paused parent's job.

    The parent's agent inputs describe the original turn. The child keeps them,
    drops what belonged to that turn only (its attachments and any earlier
    resume), writes to a new assistant message, and adds the decisions.
    """

    execution_json = dict(parent_execution_json)
    agent_inputs = dict(execution_json.get("agent_inputs") or {})
    agent_inputs.pop(RESUME_ENTRIES_KEY, None)
    agent_inputs.pop(RESUME_EXECUTION_KEY, None)
    agent_inputs.pop(ATTACHMENT_IDS_KEY, None)
    agui_context = dict(agent_inputs.get(AGUI_CONTEXT_KEY) or {})
    agui_context["assistant_message_id"] = assistant_message_id
    agent_inputs[AGUI_CONTEXT_KEY] = agui_context
    agent_inputs[RESUME_ENTRIES_KEY] = list(entries)
    agent_inputs[RESUME_EXECUTION_KEY] = dict(resume_execution)
    execution_json["agent_inputs"] = agent_inputs
    execution_json["assistant_message_id"] = assistant_message_id
    return execution_json
