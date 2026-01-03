""" execution_plan

ExecutionPlan and node/step contract types.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class ExecutionPlan:
    """Execution plan for a run."""
    
    run_id: str
    """Run ID."""
    
    mode: str
    """Execution mode (chat/bot/workflow/agent)."""
    
    plan_data: Dict[str, Any]
    """Plan data (workflow graph, agent config, etc.)."""
    
    inputs: Dict[str, Any]
    """Input parameters."""
    
    app_version_id: Optional[str] = None
    """Optional app version ID."""


@dataclass
class StepPlan:
    """Plan for a single step."""
    
    step_id: str
    """Step ID."""
    
    step_type: str
    """Step type (llm/retrieve/tool/node/plan)."""
    
    node_id: Optional[str] = None
    """Optional node ID."""
    
    input_data: Dict[str, Any] = None
    """Input data for step."""
    
    config: Optional[Dict[str, Any]] = None
    """Step configuration."""
