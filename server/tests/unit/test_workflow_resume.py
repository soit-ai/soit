"""Crash-checkpoint snapshots and resume feasibility contracts."""

from app.modules.workflow.runtime.resume import (
    CHECKPOINT_OUTPUT_LIMIT,
    RESUME_BLOCKED_CHECKPOINT_MISSING,
    RESUME_BLOCKED_OUTPUT_TRUNCATED,
    RESUME_BLOCKED_POLICY_NEVER,
    RESUME_BLOCKED_UNSAFE_NODES,
    assess_resume,
    build_checkpoint_snapshot,
    referenced_truncated_nodes,
)


def test_snapshot_keeps_only_terminal_progress() -> None:
    snapshot = build_checkpoint_snapshot(
        {"topic": "refunds"},
        {"a": "succeeded", "b": "skipped", "c": "running", "d": "failed"},
        {"a": {"value": 1}, "c": {"value": 2}, "d": {"value": 3}},
    )

    assert snapshot["inputs"] == {"topic": "refunds"}
    assert snapshot["node_states"] == {"a": "succeeded", "b": "skipped"}
    # A mid-flight node's output must never be trusted as final.
    assert snapshot["node_outputs"] == {"a": {"value": 1}}


def test_snapshot_records_oversized_outputs_instead_of_storing_them() -> None:
    snapshot = build_checkpoint_snapshot(
        {},
        {"big": "succeeded", "small": "succeeded"},
        {"big": {"blob": "x" * (CHECKPOINT_OUTPUT_LIMIT + 1)}, "small": {"ok": True}},
    )

    assert "big" not in snapshot["node_outputs"]
    assert snapshot["node_outputs"] == {"small": {"ok": True}}
    assert snapshot["truncated_node_ids"] == ["big"]


def test_truncated_output_only_blocks_when_a_remaining_node_reads_it() -> None:
    nodes = {
        "big": {"id": "big", "type": "transform"},
        "reader": {
            "id": "reader",
            "type": "transform",
            "input": {"mapping": {"v": "{{ steps.big.output.blob }}"}},
        },
        "unrelated": {"id": "unrelated", "type": "transform", "input": {"mapping": {}}},
    }
    checkpoint = {"node_states": {"big": "succeeded"}, "truncated_node_ids": ["big"]}

    assert referenced_truncated_nodes(nodes, checkpoint) == ["big"]

    # Once the reader is done too, nothing left needs the dropped output.
    finished = {
        "node_states": {"big": "succeeded", "reader": "succeeded"},
        "truncated_node_ids": ["big"],
    }
    assert referenced_truncated_nodes(nodes, finished) == []


def test_pure_and_ledger_backed_nodes_are_resumable() -> None:
    nodes = {
        "t": {"id": "t", "type": "transform"},
        "call": {"id": "call", "type": "tool"},
        "out": {"id": "out", "type": "output"},
    }
    checkpoint = {"node_states": {"t": "succeeded"}, "node_outputs": {"t": {}}}

    assert assess_resume(nodes, {}, checkpoint).resumable is True


def test_resume_is_refused_without_a_checkpoint() -> None:
    assessment = assess_resume({"t": {"id": "t", "type": "transform"}}, {}, None)

    assert assessment.resumable is False
    assert assessment.reason_code == RESUME_BLOCKED_CHECKPOINT_MISSING


def test_resume_policy_never_refuses_even_with_safe_nodes() -> None:
    assessment = assess_resume(
        {"t": {"id": "t", "type": "transform"}},
        {"resume_policy": "never"},
        {"node_states": {}},
    )

    assert assessment.resumable is False
    assert assessment.reason_code == RESUME_BLOCKED_POLICY_NEVER


def test_unknown_effectful_node_type_blocks_resume() -> None:
    # A node type outside the ledger-backed set is effectful by default and
    # has no replay guarantee, so resuming past it could repeat its effect.
    nodes = {"mystery": {"id": "mystery", "type": "mystery"}}
    assessment = assess_resume(nodes, {}, {"node_states": {}})

    assert assessment.resumable is False
    assert assessment.reason_code == RESUME_BLOCKED_UNSAFE_NODES
    assert assessment.blocking_node_ids == ["mystery"]
    assert "mystery" in (assessment.detail or "")


def test_truncated_output_blocks_resume_with_named_nodes() -> None:
    nodes = {
        "big": {"id": "big", "type": "transform"},
        "reader": {
            "id": "reader",
            "type": "transform",
            "input": {"mapping": {"v": "{{ steps.big.output.blob }}"}},
        },
    }
    checkpoint = {"node_states": {"big": "succeeded"}, "truncated_node_ids": ["big"]}

    assessment = assess_resume(nodes, {}, checkpoint)

    assert assessment.resumable is False
    assert assessment.reason_code == RESUME_BLOCKED_OUTPUT_TRUNCATED
    assert assessment.blocking_node_ids == ["big"]
