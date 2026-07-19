""" execution_plan

ExecutionPlan and node/step contract types.
"""

from dataclasses import dataclass, field
from typing import Any

from app.kernel.commons.ids import generate_run_id


@dataclass
class ExecutionPlan:
    """Execution plan for a run."""

    mode: str
    """Execution mode (chat/workflow/agent/knowledge/memory/etc.)."""

    inputs: dict[str, Any] = field(default_factory=dict[str, Any])
    """Input parameters."""

    plan_data: dict[str, Any] = field(default_factory=dict[str, Any])
    """Plan data (workflow graph, agent config, etc.)."""

    run_id: str | None = None
    """Run ID."""

    subject_kind: str | None = None
    """Execution subject kind (agent/workflow/chat/thread/knowledge/memory/etc.)."""

    subject_id: str | None = None
    """Execution subject ID."""

    subject_version_id: str | None = None
    """Optional execution subject version ID."""

    def __post_init__(self) -> None:
        """Ensure run_id is available."""
        if not self.run_id:
            self.run_id = generate_run_id()


@dataclass
class StepPlan:
    """Plan for a single step."""

    step_id: str
    """Step ID."""

    step_type: str
    """Step type (llm/retrieval/rerank/tool/workflow_node/agent_plan/memory_write/io/other)."""

    node_id: str | None = None
    """Optional node ID."""

    input_data: dict[str, Any] = field(default_factory=dict[str, Any])
    """Input data for step."""

    config: dict[str, Any] | None = None
    """Step configuration."""
