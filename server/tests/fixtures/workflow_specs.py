from __future__ import annotations

from copy import deepcopy
from typing import Any

CANONICAL_NODE_TYPES = (
    "input",
    "transform",
    "set_var",
    "llm",
    "retrieve",
    "tool",
    "condition",
    "output",
)

COMPATIBILITY_NODE_TYPES = ("http", "node")

HISTORICAL_BUILDER_TYPES = (
    "text-node",
    "prompt-node",
    "llm-node",
    "tool-node",
    "data-node",
    "output-node",
    "knowledge-search-node",
    "agent-node",
    "question-classifier-node",
    "logic-node",
    "conditional-node",
    "delivery-node",
    "loop-node",
    "transform-node",
    "code-execution-node",
    "template-transform-node",
    "variable-aggregator-node",
    "document-extractor-node",
    "variable-assignment-node",
    "parameter-extractor-node",
    "end-node",
)


def canonical_workflow_spec(
    *,
    node_type: str = "transform",
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = {
        "name": "canonical-test-workflow",
        "inputs_schema": {"type": "object", "properties": {}},
        "outputs_schema": {"type": "object", "properties": {"value": {}}},
        "graph": {
            "nodes": [
                {
                    "id": "subject",
                    "type": node_type,
                    "params": params if params is not None else {"mapping": {"value": True}},
                },
                {"id": "output", "type": "output", "params": {"value": "{{ steps.subject.output }}"}},
            ],
            "edges": [{"id": "edge-subject-output", "from": "subject", "to": "output"}],
        },
    }
    return deepcopy(spec)
