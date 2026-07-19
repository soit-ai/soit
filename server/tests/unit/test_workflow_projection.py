"""test_workflow_projection

Unit tests for workflow projection builder.
"""

from app.kernel.projections.workflow_projection import (
    build_workflow_components,
    build_workflow_edges,
    build_workflow_refs,
)


def _sample_spec() -> dict:
    return {
        "name": "demo",
        "inputs_schema": {},
        "outputs_schema": {},
        "graph": {
            "nodes": [
                {
                    "id": "tool1",
                    "type": "tool",
                    "params": {
                        "tool_ref": "tool:http:demo",
                        "arguments": {"knowledge_ref": "knowledge:kb_1"},
                    },
                },
                {
                    "id": "llm1",
                    "type": "llm",
                    "params": {"model": "model:openai:gpt-4", "prompt": "Summarize the result."},
                },
            ],
            "edges": [
                {"id": "e1", "from": "tool1", "to": "llm1", "condition": "{{ steps.tool1.output.ok }}"}
            ],
        },
    }


def test_build_components_edges_refs():
    spec = _sample_spec()

    components = build_workflow_components(spec)
    edges = build_workflow_edges(spec)
    refs = build_workflow_refs(spec)

    assert len(components) == 2
    assert {c["component_id"] for c in components} == {"tool1", "llm1"}

    assert len(edges) == 1
    assert edges[0]["from_component_id"] == "tool1"
    assert edges[0]["to_component_id"] == "llm1"
    assert edges[0]["edge_spec_json"]["condition"] == "{{ steps.tool1.output.ok }}"

    ref_types = {(r["ref_type"], r.get("ref_key") or r.get("ref_id")) for r in refs}
    assert ("tool", "tool:http:demo") in ref_types
    assert ("knowledge", "knowledge:kb_1") in ref_types
    assert ("model", "model:openai:gpt-4") in ref_types


def test_build_workflow_refs_ignores_legacy_app_refs():
    spec = {
        "name": "demo",
        "inputs_schema": {},
        "outputs_schema": {},
        "graph": {
            "nodes": [
                {
                    "id": "legacy-app",
                    "type": "tool",
                    "params": {"app_ref": "app:legacy-entry"},
                }
            ],
            "edges": [],
        },
    }

    assert build_workflow_refs(spec) == []
