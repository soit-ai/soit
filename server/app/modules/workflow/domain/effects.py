"""Node side-effect semantics for workflow resume decisions.

Every node type carries an effect class that states what re-entering the
node can do to the outside world. Resume machinery uses this vocabulary to
decide whether an interrupted run may continue; nothing here executes.
"""

from typing import Any

EFFECT_PURE = "pure"
EFFECT_READ = "read"
EFFECT_EFFECTFUL = "effectful"

EFFECT_CLASSES = (EFFECT_PURE, EFFECT_READ, EFFECT_EFFECTFUL)

ON_RESUME_FAIL = "fail"
ON_RESUME_REQUIRE_APPROVAL = "require_approval"

ON_RESUME_MODES = (ON_RESUME_FAIL, ON_RESUME_REQUIRE_APPROVAL)

RESUME_POLICY_NEVER = "never"
RESUME_POLICY_MANUAL = "manual"
RESUME_POLICY_AUTO = "auto"

RESUME_POLICIES = (RESUME_POLICY_NEVER, RESUME_POLICY_MANUAL, RESUME_POLICY_AUTO)
DEFAULT_RESUME_POLICY = RESUME_POLICY_MANUAL

DEFAULT_NODE_EFFECT_CLASS: dict[str, str] = {
    "input": EFFECT_PURE,
    "transform": EFFECT_PURE,
    "set_var": EFFECT_PURE,
    "condition": EFFECT_PURE,
    "output": EFFECT_PURE,
    "llm": EFFECT_READ,
    "retrieve": EFFECT_READ,
    "tool": EFFECT_EFFECTFUL,
    "http": EFFECT_EFFECTFUL,
    "node": EFFECT_EFFECTFUL,
}

# Only nodes that reach external systems may narrow their class, and never
# below read: a node that leaves the process can always at minimum observe.
_OVERRIDABLE_NODE_TYPES = frozenset({"tool", "http", "node"})
_ALLOWED_OVERRIDES = frozenset({EFFECT_READ, EFFECT_EFFECTFUL})


def resolve_node_effect_class(node: dict[str, Any]) -> str:
    """Return the effect class governing re-entry of this node."""

    node_type = str(node.get("type") or "")
    default = DEFAULT_NODE_EFFECT_CLASS.get(node_type, EFFECT_EFFECTFUL)
    override = node.get("effect_class")
    if (
        override in _ALLOWED_OVERRIDES
        and node_type in _OVERRIDABLE_NODE_TYPES
    ):
        return str(override)
    return default


def resolve_node_on_resume(node: dict[str, Any]) -> str:
    """Return how resume treats this node when replay safety is unproven."""

    mode = node.get("on_resume")
    if mode in ON_RESUME_MODES:
        return str(mode)
    return ON_RESUME_FAIL


def resolve_resume_policy(semantics: dict[str, Any] | None) -> str:
    """Return the workflow-level resume policy, defaulting to manual."""

    policy = (semantics or {}).get("resume_policy")
    if policy in RESUME_POLICIES:
        return str(policy)
    return DEFAULT_RESUME_POLICY
