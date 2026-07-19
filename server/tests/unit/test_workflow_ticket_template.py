"""Tests for the ticket triage workflow template."""

import pytest

from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.templates.ticket_triage import build_ticket_triage_template


def test_ticket_triage_template_contains_mvp_nodes_and_valid_edges():
    spec = build_ticket_triage_template()

    nodes = spec["graph"]["nodes"]
    node_ids = [node["id"] for node in nodes]
    assert node_ids == [
        "start",
        "knowledge_search",
        "classify",
        "approval",
        "ticket_tool",
        "response",
        "reject",
    ]

    node_id_set = set(node_ids)
    for edge in spec["graph"]["edges"]:
        assert edge["from"] in node_id_set
        assert edge["to"] in node_id_set

    properties = spec["inputs_schema"]["properties"]
    assert set(spec["inputs_schema"]["required"]) == {"customer_message", "customer_id", "priority"}
    assert properties["customer_message"]["type"] == "string"
    assert properties["customer_id"]["type"] == "string"
    assert properties["priority"]["type"] == "string"
    assert properties["knowledge_collection"]["type"] == "string"
    assert properties["embedding_model"]["type"] == "string"
    assert properties["model_ref"]["type"] == "string"
    ticket_node = next(node for node in nodes if node["id"] == "ticket_tool")
    assert ticket_node["params"]["tool_ref"] == "builtin.ticket.create_review_ticket"
    assert ticket_node["params"]["customer_id"] == "{{ steps.start.output.customer_id }}"
    assert "parameters" not in ticket_node["params"]

    approval_node = next(node for node in nodes if node["id"] == "approval")
    assert approval_node["params"]["condition"] == '{{ inputs.priority }} != "low"'

    approval_edges = [edge for edge in spec["graph"]["edges"] if edge["from"] == "approval"]
    assert approval_edges == [
        {
            "id": "e_approval_ticket",
            "from": "approval",
            "to": "ticket_tool",
            "condition": "{{ steps.approval.output.result }}",
        },
        {
            "id": "e_approval_reject",
            "from": "approval",
            "to": "reject",
            "condition": "{{ steps.approval.output.result }} == false",
        },
    ]
    conditions = [edge.get("condition") for edge in spec["graph"]["edges"] if edge["from"] == "approval"]
    assert "{{ steps.approval.output.result }}" in conditions
    assert "{{ steps.approval.output.result }} == false" in conditions
    assert conditions.count("true") == 0
    assert conditions.count("false") == 0

    reject_node = next(node for node in nodes if node["id"] == "reject")
    assert reject_node["type"] == "output"
    assert reject_node["params"] == {
        "ticket_id": "",
        "status": "rejected",
        "response": "Ticket creation skipped because the approval condition was not met.",
        "citations": "{{ steps.knowledge_search.output.citations }}",
    }
    assert all(edge["from"] != "response" for edge in spec["graph"]["edges"])


@pytest.mark.asyncio
async def test_workflow_service_creates_ticket_triage_draft(db, ctx):
    service = WorkflowService(db=db, ctx=ctx)

    workflow = await service.create_ticket_triage_template(name="Ticket triage unit")
    version = await service.get_current_version(workflow.id)

    assert workflow.name == "Ticket triage unit"
    assert workflow.published_version_id is None
    assert workflow.metadata_json["template_key"] == "ticket_triage"
    assert version is not None
    assert version.status == "draft"
    assert [node["id"] for node in version.spec_json["graph"]["nodes"]] == [
        "start",
        "knowledge_search",
        "classify",
        "approval",
        "ticket_tool",
        "response",
        "reject",
    ]
