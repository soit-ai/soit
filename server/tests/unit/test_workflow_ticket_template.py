"""Tests for the ticket triage workflow template."""

import pytest

from app.modules.workflow.application.schemas import WorkflowCreate
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
    assert set(spec["inputs_schema"]["required"]) == {
        "customer_message",
        "customer_id",
        "priority",
        "ticket_secret_id",
    }
    assert properties["customer_message"]["type"] == "string"
    assert properties["customer_id"]["type"] == "string"
    assert properties["priority"]["type"] == "string"
    assert properties["ticket_secret_id"]["pattern"].startswith("^sec_")
    assert "knowledge_collection" not in properties
    assert "embedding_model" not in properties
    assert "model_ref" not in properties

    start_node = next(node for node in nodes if node["id"] == "start")
    assert start_node == {"id": "start", "type": "input", "params": {}}

    retrieve_node = next(node for node in nodes if node["id"] == "knowledge_search")
    assert retrieve_node["params"]["knowledge_ref"] == "knowledge:configure-me"
    assert "collection" not in retrieve_node["params"]
    assert "embedding_model" not in retrieve_node["params"]

    classify_node = next(node for node in nodes if node["id"] == "classify")
    assert classify_node["params"]["model"] == "model:configure-me"
    ticket_node = next(node for node in nodes if node["id"] == "ticket_tool")
    assert ticket_node["params"]["tool_ref"] == "builtin.ticket.create_review_ticket"
    assert ticket_node["params"]["arguments"] == {
        "customer_id": "{{ steps.start.output.customer_id }}",
        "priority": "{{ steps.start.output.priority }}",
        "message": "{{ steps.start.output.customer_message }}",
        "classification": "{{ steps.classify.output.text }}",
        "api_token": {"secret_id": "{{ inputs.ticket_secret_id }}"},
    }
    assert set(ticket_node["params"]) == {"tool_ref", "arguments"}

    approval_node = next(node for node in nodes if node["id"] == "approval")
    assert approval_node["params"] == {
        "condition": '{{ inputs.priority }} != "low"'
    }

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
        "value": {
            "ticket_id": "",
            "status": "rejected",
            "response": "Ticket creation skipped because the approval condition was not met.",
            "citations": "{{ steps.knowledge_search.output.citations }}",
        },
    }
    response_node = next(node for node in nodes if node["id"] == "response")
    assert set(response_node["params"]) == {"value"}
    assert spec["outputs_schema"]["required"] == ["value"]
    assert spec["outputs_schema"]["properties"]["value"]["type"] == "object"
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


@pytest.mark.asyncio
async def test_workflow_service_creates_a_schema_valid_default_draft(db, ctx):
    service = WorkflowService(db=db, ctx=ctx)

    workflow = await service.create_workflow(WorkflowCreate(name="Default workflow unit"))
    version = await service.get_current_version(workflow.id)

    assert version is not None
    assert version.status == "draft"
    transform = next(
        node for node in version.spec_json["graph"]["nodes"] if node["type"] == "transform"
    )
    assert transform["params"] == {"mapping": {}}
