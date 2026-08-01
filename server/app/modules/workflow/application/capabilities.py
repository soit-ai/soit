"""Canonical workflow node capability contract."""

from dataclasses import dataclass

from app.modules.workflow.domain.effects import DEFAULT_NODE_EFFECT_CLASS


@dataclass(frozen=True, slots=True)
class WorkflowNodeCapability:
    """Metadata for one backend-supported workflow node type."""

    type: str
    ui_type: str
    category: str
    executable: bool
    effect_class: str


def _effect(node_type: str) -> str:
    return DEFAULT_NODE_EFFECT_CLASS[node_type]


WORKFLOW_NODE_CAPABILITIES: tuple[WorkflowNodeCapability, ...] = (
    WorkflowNodeCapability(
        type="input",
        ui_type="input-node",
        category="input",
        executable=True,
        effect_class=_effect("input"),
    ),
    WorkflowNodeCapability(
        type="transform",
        ui_type="transform-node",
        category="data",
        executable=True,
        effect_class=_effect("transform"),
    ),
    WorkflowNodeCapability(
        type="set_var",
        ui_type="variable-assignment-node",
        category="data",
        executable=True,
        effect_class=_effect("set_var"),
    ),
    WorkflowNodeCapability(
        type="llm",
        ui_type="llm-node",
        category="model",
        executable=True,
        effect_class=_effect("llm"),
    ),
    WorkflowNodeCapability(
        type="retrieve",
        ui_type="knowledge-search-node",
        category="data",
        executable=True,
        effect_class=_effect("retrieve"),
    ),
    WorkflowNodeCapability(
        type="tool",
        ui_type="tool-node",
        category="tool",
        executable=True,
        effect_class=_effect("tool"),
    ),
    WorkflowNodeCapability(
        type="condition",
        ui_type="conditional-node",
        category="flow",
        executable=True,
        effect_class=_effect("condition"),
    ),
    WorkflowNodeCapability(
        type="output",
        ui_type="output-node",
        category="output",
        executable=True,
        effect_class=_effect("output"),
    ),
)

BUILDER_NODE_TYPES: tuple[str, ...] = tuple(capability.type for capability in WORKFLOW_NODE_CAPABILITIES)
COMPATIBILITY_NODE_TYPES: tuple[str, ...] = ("http", "node")


def get_workflow_node_capabilities() -> tuple[WorkflowNodeCapability, ...]:
    """Return the immutable canonical workflow node capabilities."""

    return WORKFLOW_NODE_CAPABILITIES
