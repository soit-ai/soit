"""Crash-checkpoint snapshots and resume feasibility.

A workflow run can only be resumed when re-entering every unfinished node is
provably safe. That proof is machine-checked here from the node effect
vocabulary, never assumed: pure and read nodes are safe by class, externally
reaching nodes are safe only because their calls go through the durable
tool-call ledger and replay instead of re-executing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.modules.workflow.domain.effects import (
    EFFECT_EFFECTFUL,
    RESUME_POLICY_NEVER,
    resolve_node_effect_class,
    resolve_resume_policy,
)

CHECKPOINT_OUTPUT_LIMIT = 8192
"""Serialized size cap per stored node output, matching RunStep summaries."""

# Node types whose external calls run through the durable tool-call ledger
# with an attempt-stable identity, so a re-entered node replays completed
# side effects instead of reissuing them.
LEDGER_BACKED_NODE_TYPES = frozenset({"tool", "http", "node"})

RESUME_BLOCKED_POLICY_NEVER = "WORKFLOW_RESUME_POLICY_NEVER"
RESUME_BLOCKED_CHECKPOINT_MISSING = "WORKFLOW_RESUME_CHECKPOINT_MISSING"
RESUME_BLOCKED_OUTPUT_TRUNCATED = "WORKFLOW_RESUME_OUTPUT_TRUNCATED"
RESUME_BLOCKED_UNSAFE_NODES = "WORKFLOW_RESUME_UNSAFE_NODES"


def build_checkpoint_snapshot(
    inputs: dict[str, Any] | None,
    node_states: dict[str, str],
    node_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Freeze terminal node progress into a resumable snapshot.

    Only terminal states are stored — a mid-flight node must be re-entered on
    resume, never trusted. Outputs above the size cap are dropped and their
    node recorded, so a resume that needs them fails explicitly instead of
    silently reading wrong data.
    """

    stored_outputs: dict[str, Any] = {}
    truncated: list[str] = []
    for node_id, output in node_outputs.items():
        if node_states.get(node_id) != "succeeded":
            continue
        try:
            serialized = json.dumps(output, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            truncated.append(node_id)
            continue
        if len(serialized) > CHECKPOINT_OUTPUT_LIMIT:
            truncated.append(node_id)
            continue
        stored_outputs[node_id] = output
    return {
        "inputs": dict(inputs or {}),
        "node_states": {
            node_id: status
            for node_id, status in node_states.items()
            if status in {"succeeded", "skipped"}
        },
        "node_outputs": stored_outputs,
        "truncated_node_ids": sorted(truncated),
    }


def _remaining_node_ids(
    nodes: dict[str, dict[str, Any]],
    checkpoint: dict[str, Any],
) -> list[str]:
    terminal = {
        str(node_id)
        for node_id, status in dict(checkpoint.get("node_states") or {}).items()
        if status in {"succeeded", "skipped"}
    }
    return [node_id for node_id in nodes if node_id not in terminal]


def referenced_truncated_nodes(
    nodes: dict[str, dict[str, Any]],
    checkpoint: dict[str, Any],
) -> list[str]:
    """Truncated nodes whose output a remaining node still references."""

    truncated = [str(t) for t in checkpoint.get("truncated_node_ids") or []]
    if not truncated:
        return []
    referenced: set[str] = set()
    for node_id in _remaining_node_ids(nodes, checkpoint):
        node = nodes.get(node_id) or {}
        raw = json.dumps(
            node.get("input") or node.get("params") or {},
            ensure_ascii=False,
            default=str,
        )
        for truncated_id in truncated:
            if f"steps.{truncated_id}" in raw:
                referenced.add(truncated_id)
    return sorted(referenced)


@dataclass(frozen=True)
class ResumeAssessment:
    """Machine-checked verdict on whether a run may resume."""

    resumable: bool
    reason_code: str | None = None
    blocking_node_ids: list[str] = field(default_factory=list)

    @property
    def detail(self) -> str | None:
        if self.resumable:
            return None
        if self.reason_code == RESUME_BLOCKED_POLICY_NEVER:
            return "The workflow declares resume_policy=never"
        if self.reason_code == RESUME_BLOCKED_CHECKPOINT_MISSING:
            return "No crash checkpoint was recorded before the failure"
        if self.reason_code == RESUME_BLOCKED_OUTPUT_TRUNCATED:
            return (
                "Remaining nodes reference checkpoint outputs that were too "
                f"large to store: {', '.join(self.blocking_node_ids)}"
            )
        if self.reason_code == RESUME_BLOCKED_UNSAFE_NODES:
            return (
                "Re-entering these nodes could repeat external side effects: "
                f"{', '.join(self.blocking_node_ids)}"
            )
        return self.reason_code


def assess_resume(
    nodes: dict[str, dict[str, Any]],
    semantics: dict[str, Any] | None,
    checkpoint: dict[str, Any] | None,
) -> ResumeAssessment:
    """Decide whether resuming this run is provably safe."""

    if resolve_resume_policy(semantics) == RESUME_POLICY_NEVER:
        return ResumeAssessment(False, RESUME_BLOCKED_POLICY_NEVER)
    if not checkpoint or not isinstance(checkpoint.get("node_states"), dict):
        return ResumeAssessment(False, RESUME_BLOCKED_CHECKPOINT_MISSING)

    unsafe: list[str] = []
    for node_id in _remaining_node_ids(nodes, checkpoint):
        node = nodes.get(node_id) or {}
        if resolve_node_effect_class(node) != EFFECT_EFFECTFUL:
            continue
        if str(node.get("type") or "") in LEDGER_BACKED_NODE_TYPES:
            continue
        unsafe.append(node_id)
    if unsafe:
        return ResumeAssessment(False, RESUME_BLOCKED_UNSAFE_NODES, sorted(unsafe))

    truncated = referenced_truncated_nodes(nodes, checkpoint)
    if truncated:
        return ResumeAssessment(False, RESUME_BLOCKED_OUTPUT_TRUNCATED, truncated)

    return ResumeAssessment(True)
