"""Entrypoint tests for workspace-scoped global search."""

from fastapi import status

from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.threads import Thread
from app.modules.agent.domain.models import Agent
from app.modules.knowledge.domain.models import Knowledge
from app.modules.modelhub.domain.models import ProviderModel
from app.modules.plugin.domain.models import Plugin
from app.modules.workflow.domain.models import Workflow


def _seed_searchable_resources(db) -> None:
    scope = {"tenant_id": "test-tenant", "workspace_id": "test-workspace"}
    db.add_all(
        [
            Agent(
                id="agt_customer",
                name="Customer support agent",
                description="Answers customer questions",
                **scope,
            ),
            Workflow(
                id="wf_customer",
                name="Customer triage workflow",
                description="Routes incoming customer requests",
                **scope,
            ),
            Knowledge(
                id="knw_customer",
                name="Customer knowledge",
                description="Support policies and answers",
                **scope,
            ),
            Plugin(
                id="plg_customer",
                name="Customer toolkit",
                version="1.0.0",
                description="Customer support tools",
                spec_json={},
                manifest_json={},
                **scope,
            ),
            ProviderModel(
                id="pmod_customer",
                provider_id="prov_openai",
                provider_kind="openai",
                model_id="customer-gpt",
                display_name="Customer GPT",
                description="Model for customer conversations",
                **scope,
            ),
            Thread(
                id="thr_customer",
                agent_id="agt_customer",
                title="Customer incident",
                summary="Escalation from a customer conversation",
                owner_user_id="test-user",
                **scope,
            ),
            Run(
                id="run_customer",
                mode="agent",
                kind="agent",
                subject_kind="agent",
                subject_id="agt_customer",
                status="succeeded",
                input_summary="Customer asked for a refund",
                user_id="test-user",
                **scope,
            ),
            Agent(
                id="agt_outside",
                tenant_id="test-tenant",
                workspace_id="other-workspace",
                name="Customer data from another workspace",
            ),
        ]
    )
    db.commit()


def test_global_search_aggregates_supported_workspace_resources(client, db) -> None:
    _seed_searchable_resources(db)

    response = client.get("/api/v1/search", params={"q": "customer", "limit": 5})

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["query"] == "customer"
    assert {item["kind"] for item in payload["items"]} == {
        "agent",
        "workflow",
        "knowledge",
        "plugin",
        "model",
        "thread",
        "run",
    }
    assert payload["counts"] == {
        "agent": 1,
        "workflow": 1,
        "knowledge": 1,
        "plugin": 1,
        "model": 1,
        "thread": 1,
        "run": 1,
    }
    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id["agt_customer"]["url"] == "/agents/agt_customer"
    assert by_id["wf_customer"]["url"] == "/workflow/wf_customer/build"
    assert by_id["knw_customer"]["url"] == "/knowledge/knw_customer"
    assert by_id["thr_customer"]["url"] == "/chat/agt_customer/thr_customer"
    assert by_id["run_customer"]["url"] == "/observe/runs/run_customer"
    assert "agt_outside" not in by_id


def test_global_search_can_filter_resource_kinds(client, db) -> None:
    _seed_searchable_resources(db)

    response = client.get(
        "/api/v1/search",
        params=[("q", "customer"), ("types", "agent"), ("types", "workflow")],
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert {item["kind"] for item in payload["items"]} == {"agent", "workflow"}
    assert payload["counts"] == {"agent": 1, "workflow": 1}


def test_global_search_treats_like_wildcards_as_literal_text(client, db) -> None:
    _seed_searchable_resources(db)

    response = client.get("/api/v1/search", params={"q": "%%"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["items"] == []


def test_global_search_validates_query_and_resource_kind(client) -> None:
    too_short = client.get("/api/v1/search", params={"q": "x"})
    invalid_type = client.get(
        "/api/v1/search",
        params={"q": "customer", "types": "unknown"},
    )

    assert too_short.status_code == status.HTTP_400_BAD_REQUEST
    assert invalid_type.status_code == status.HTTP_400_BAD_REQUEST
