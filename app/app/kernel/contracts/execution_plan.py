""" execution_plan

ExecutionPlan and node/step contract types.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from app.kernel.commons.ids import generate_run_id


@dataclass
class ExecutionPlan:
    """Execution plan for a run."""

    mode: str
    """Execution mode (chat/bot/workflow/agent)."""

    inputs: Dict[str, Any] = field(default_factory=dict)
    """Input parameters."""

    plan_data: Dict[str, Any] = field(default_factory=dict)
    """Plan data (workflow graph, agent config, etc.)."""

    run_id: Optional[str] = None
    """Run ID."""

    app_id: Optional[str] = None
    """App ID."""

    app_version_id: Optional[str] = None
    """Optional app version ID."""

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
    
    node_id: Optional[str] = None
    """Optional node ID."""
    
    input_data: Dict[str, Any] = field(default_factory=dict)
    """Input data for step."""
    
    config: Optional[Dict[str, Any]] = None
    """Step configuration."""
