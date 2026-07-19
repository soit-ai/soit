"""Canonical workflow node capability contract."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowNodeCapability:
    """Metadata for one backend-supported workflow node type."""

    type: str
    ui_type: str
    category: str
    executable: bool


WORKFLOW_NODE_CAPABILITIES: tuple[WorkflowNodeCapability, ...] = (
    WorkflowNodeCapability(type="input", ui_type="input-node", category="input", executable=True),
    WorkflowNodeCapability(type="transform", ui_type="transform-node", category="data", executable=True),
    WorkflowNodeCapability(
        type="set_var",
        ui_type="variable-assignment-node",
        category="data",
        executable=True,
    ),
    WorkflowNodeCapability(type="llm", ui_type="llm-node", category="model", executable=True),
    WorkflowNodeCapability(
        type="retrieve",
        ui_type="knowledge-search-node",
        category="data",
        executable=True,
    ),
    WorkflowNodeCapability(type="tool", ui_type="tool-node", category="tool", executable=True),
    WorkflowNodeCapability(
        type="condition",
        ui_type="conditional-node",
        category="flow",
        executable=True,
    ),
    WorkflowNodeCapability(type="output", ui_type="output-node", category="output", executable=True),
)

BUILDER_NODE_TYPES: tuple[str, ...] = tuple(capability.type for capability in WORKFLOW_NODE_CAPABILITIES)
COMPATIBILITY_NODE_TYPES: tuple[str, ...] = ("http", "node")


def get_workflow_node_capabilities() -> tuple[WorkflowNodeCapability, ...]:
    """Return the immutable canonical workflow node capabilities."""

    return WORKFLOW_NODE_CAPABILITIES
