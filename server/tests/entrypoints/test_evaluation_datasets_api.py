"""Evaluation dataset API entrypoint tests."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi import status

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.evaluation.application.dataset_service import RegressionDatasetService
from app.modules.evaluation.application.service import RegressionEvaluationService

BASE = "/api/v1/evaluations"
MODEL = "model:test:current"


class _LLM(LLMPort):
    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return ChatResponse(text="Refunds take 14 days.", tokens_prompt=3, tokens_completion=5, finish_reason="stop")

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class _Tools(ToolPort):
    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={})


@contextmanager
def _as_context(ctx: RequestContext):
    previous = app.dependency_overrides.get(get_current_context)

    async def _override() -> RequestContext:
        return ctx

    app.dependency_overrides[get_current_context] = _override
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_context, None)
        else:
            app.dependency_overrides[get_current_context] = previous


@pytest.fixture(autouse=True)
def _agents(async_db, ctx):
    async def build() -> AgentApplicationService:
        return AgentApplicationService(
            db=async_db,
            ctx=ctx,
            llm_port=_LLM(),
            tool_port=_Tools(),
            regression_evaluator=RegressionEvaluationService(db=async_db, ctx=ctx),
        )

    app.dependency_overrides[get_agent_application_service] = build
    yield
    app.dependency_overrides.pop(get_agent_application_service, None)


async def _agent(async_client, name: str = "support", *, publish: bool = True) -> str:
    agent_id = (await async_client.post("/api/v1/agents", json={"name": name})).json()["data"]["id"]
    version = await async_client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={"system_prompt": "Answer policy questions.", "bindings": {"model_ref": MODEL}},
    )
    version_id = version.json()["data"]["id"]
    if publish:
        published = await async_client.post(f"/api/v1/agents/{agent_id}/publish", json={"version_id": version_id})
        assert published.status_code == 200, published.text
    return agent_id


async def _dataset(async_client, agent_id: str, name: str = "refunds") -> dict:
    response = await async_client.post(
        f"{BASE}/datasets", json={"subject_id": agent_id, "name": name, "description": "Policy questions"}
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]


def _case(name: str, term: str = "14 days") -> dict:
    return {"name": name, "input": f"Question {name}", "expected_features": {"minimum_output_terms": [term]}}


@pytest.mark.asyncio
async def test_a_dataset_is_created_listed_described_and_archived(async_client) -> None:
    agent_id = await _agent(async_client)

    created = await _dataset(async_client, agent_id)
    assert created["revision"] == 1 and created["case_count"] == 0 and created["latest_report"] is None
    assert created["subject_id"] == agent_id and created["status"] == "active"

    listed = await async_client.get(f"{BASE}/datasets", params={"subject_id": agent_id})
    assert [item["id"] for item in listed.json()["data"]] == [created["id"]]

    patched = await async_client.patch(f"{BASE}/datasets/{created['id']}", json={"description": "Edited"})
    assert patched.json()["data"]["description"] == "Edited"
    assert patched.json()["data"]["revision"] == 1

    duplicate = await async_client.post(f"{BASE}/datasets", json={"subject_id": agent_id, "name": "refunds"})
    assert duplicate.status_code == status.HTTP_409_CONFLICT

    archived = await async_client.delete(f"{BASE}/datasets/{created['id']}")
    assert archived.status_code == status.HTTP_200_OK
    assert archived.json()["data"]["status"] == "archived"
    assert (await async_client.get(f"{BASE}/datasets")).json()["data"] == []
    everything = await async_client.get(f"{BASE}/datasets", params={"status": ""})
    assert [item["id"] for item in everything.json()["data"]] == [created["id"]]
    restored = await async_client.patch(f"{BASE}/datasets/{created['id']}", json={"status": "active"})
    assert restored.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_a_dataset_needs_an_agent_that_exists_in_the_workspace(async_client) -> None:
    response = await async_client.post(f"{BASE}/datasets", json={"subject_id": "agt_missing", "name": "x"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert (await async_client.get(f"{BASE}/datasets/regds_missing")).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_cases_are_added_edited_listed_and_removed_with_revisions(async_client) -> None:
    dataset = await _dataset(async_client, await _agent(async_client))
    url = f"{BASE}/datasets/{dataset['id']}"

    one = await async_client.post(f"{url}/cases", json=_case("one"))
    two = await async_client.post(f"{url}/cases", json={**_case("two"), "note": "second"})
    assert one.status_code == two.status_code == status.HTTP_201_CREATED
    one_case, two_case = one.json()["data"], two.json()["data"]
    assert one_case["input"] == "Question one"
    assert one_case["source_run_id"] is None
    assert (one_case["dataset_revision"], two_case["dataset_revision"]) == (2, 3)
    assert one_case["dataset"] == "refunds"

    page = await async_client.get(f"{url}/cases", params={"page_size": 1, "with_total": "true"})
    body = page.json()["data"]
    assert [item["id"] for item in body["items"]] == [one_case["id"]]
    assert body["total"] == 2 and body["next_page_token"]
    rest = await async_client.get(f"{url}/cases", params={"page_size": 1, "page_token": body["next_page_token"]})
    assert [item["id"] for item in rest.json()["data"]["items"]] == [two_case["id"]]
    found = await async_client.get(f"{url}/cases", params={"q": "TWO"})
    assert [item["name"] for item in found.json()["data"]["items"]] == ["two"]

    edited = await async_client.patch(
        f"{url}/cases/{one_case['id']}",
        json={"expected_features": {"max_latency_ms": 1500, "llm_judge": {"rubric": "Polite", "min_score": 0.9}}},
    )
    assert edited.status_code == status.HTTP_200_OK, edited.text
    assert edited.json()["data"]["dataset_revision"] == 4
    assert edited.json()["data"]["expected_features_json"]["llm_judge"]["rubric"] == "Polite"
    fetched = await async_client.get(f"{url}/cases/{one_case['id']}")
    assert fetched.json()["data"]["name"] == "one"

    invalid = await async_client.patch(f"{url}/cases/{one_case['id']}", json={"expected_features": {"bogus": 1}})
    assert invalid.status_code == status.HTTP_400_BAD_REQUEST
    clash = await async_client.post(f"{url}/cases", json=_case("two"))
    assert clash.status_code == status.HTTP_409_CONFLICT

    removed = await async_client.delete(f"{url}/cases/{two_case['id']}")
    assert removed.json()["data"]["revision"] == 5 and removed.json()["data"]["case_count"] == 1
    assert (await async_client.get(f"{url}/cases/{two_case['id']}")).status_code == status.HTTP_404_NOT_FOUND

    versions = (await async_client.get(f"{url}/versions")).json()["data"]
    assert [item["revision"] for item in versions] == [5, 4, 3, 2, 1]
    assert versions[0]["changes"] == {"added": 0, "removed": 1, "changed": 0}
    assert "snapshot" not in versions[0]
    detail = (await async_client.get(f"{url}/versions/3")).json()["data"]
    assert [item["name"] for item in detail["snapshot"]] == ["one", "two"]
    assert (await async_client.get(f"{url}/versions/99")).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_import_reports_every_bad_line_and_export_round_trips(async_client) -> None:
    agent_id = await _agent(async_client)
    source = await _dataset(async_client, agent_id, "source")
    target = await _dataset(async_client, agent_id, "target")

    lines = [
        json.dumps(_case("plain")),
        json.dumps(
            {
                "name": "chat",
                "input": {"messages": [{"role": "user", "content": "hello"}]},
                "expected_features": {"max_cost_amount": 0.5},
            }
        ),
    ]
    bad = await async_client.post(
        f"{BASE}/datasets/{source['id']}/import",
        json={"content": "\n".join([lines[0], "nope", json.dumps({"name": "n", "input": "i"})])},
    )
    assert bad.status_code == status.HTTP_400_BAD_REQUEST
    assert [item["line"] for item in bad.json()["details"]["errors"]] == [2, 3]
    unchanged = (await async_client.get(f"{BASE}/datasets/{source['id']}")).json()["data"]
    assert (unchanged["revision"], unchanged["case_count"]) == (1, 0)

    ok = await async_client.post(
        f"{BASE}/datasets/{source['id']}/import", json={"content": "\n".join(lines) + "\n", "note": "seed"}
    )
    assert ok.status_code == status.HTTP_201_CREATED, ok.text
    assert ok.json()["data"]["imported"] == 2
    assert ok.json()["data"]["dataset"]["revision"] == 2

    exported = await async_client.get(f"{BASE}/datasets/{source['id']}/export")
    assert exported.status_code == status.HTTP_200_OK
    assert exported.headers["content-type"].startswith("application/x-ndjson")
    assert "soit-dataset-source.jsonl" in exported.headers["content-disposition"]
    assert [json.loads(line)["name"] for line in exported.text.splitlines()] == ["plain", "chat"]

    again = await async_client.post(f"{BASE}/datasets/{target['id']}/import", json={"content": exported.text})
    assert again.status_code == status.HTTP_201_CREATED
    back = await async_client.get(f"{BASE}/datasets/{target['id']}/export")
    assert back.text == exported.text
    first = (await async_client.get(f"{BASE}/datasets/{source['id']}/versions")).json()["data"][0]
    second = (await async_client.get(f"{BASE}/datasets/{target['id']}/versions")).json()["data"][0]
    assert first["content_hash"] == second["content_hash"] and first["note"] == "seed"

    duplicate = await async_client.post(f"{BASE}/datasets/{target['id']}/import", json={"content": lines[0]})
    assert duplicate.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_an_imported_dataset_runs_and_its_reports_are_listed_with_their_results(async_client) -> None:
    agent_id = await _agent(async_client)
    dataset = await _dataset(async_client, agent_id, "refunds")
    url = f"{BASE}/datasets/{dataset['id']}"
    content = "\n".join(
        json.dumps(item) for item in (_case("refunds-window"), _case("tone", "never-said"))
    )
    await async_client.post(f"{url}/import", json={"content": content})

    run = await async_client.post(f"{BASE}/run", json={"subject_id": agent_id, "dataset": "refunds"})

    assert run.status_code == status.HTTP_201_CREATED, run.text
    report = run.json()["data"]
    assert report["dataset"] == "refunds" and report["dataset_revision"] == 2
    assert report["baseline_report_id"] is None
    assert report["summary_json"]["total"] == 2 and report["summary_json"]["passed"] == 1

    refreshed = (await async_client.get(url)).json()["data"]
    latest = refreshed["latest_report"]
    assert latest["id"] == report["id"] and latest["passed"] is False
    assert (latest["total"], latest["passed_count"], latest["pass_rate"]) == (2, 1, 0.5)

    second = (await async_client.post(f"{BASE}/run", json={"subject_id": agent_id, "dataset": "refunds"})).json()["data"]
    assert second["baseline_report_id"] == report["id"]

    listing = await async_client.get(
        f"{BASE}/reports", params={"subject_id": agent_id, "dataset": "refunds", "with_total": "true", "page_size": 1}
    )
    body = listing.json()["data"]
    assert body["total"] == 2 and [item["id"] for item in body["items"]] == [second["id"]]
    assert "case_results_json" not in body["items"][0]
    assert body["items"][0]["baseline_report_id"] == report["id"]
    assert body["next_page_token"]
    failing = await async_client.get(f"{BASE}/reports", params={"passed": "false", "dataset": "other"})
    assert failing.json()["data"]["items"] == []

    full = (await async_client.get(f"{BASE}/reports/{report['id']}")).json()["data"]
    assert len(full["case_results_json"]) == 2
    assert {item["name"] for item in full["case_results_json"]} == {"refunds-window", "tone"}
    assert (await async_client.get(f"{BASE}/reports/regrep_missing")).status_code == status.HTTP_404_NOT_FOUND

    await async_client.delete(url)
    gone = await async_client.post(f"{BASE}/run", json={"subject_id": agent_id, "dataset": "refunds"})
    assert gone.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_a_dataset_name_without_a_dataset_row_still_runs(async_client, async_db, ctx) -> None:
    """Cases written before datasets existed keep running by name."""
    from app.modules.evaluation.domain.models import RegressionCase

    agent_id = await _agent(async_client)
    async_db.add(
        RegressionCase(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            subject_kind="agent",
            subject_id=agent_id,
            source_run_id="run_legacy",
            name="legacy",
            dataset="legacy-set",
            input_snapshot_json={"input": "Question legacy"},
            expected_features_json={"minimum_output_terms": ["14 days"]},
        )
    )
    await async_db.commit()

    run = await async_client.post(f"{BASE}/run", json={"subject_id": agent_id, "dataset": "legacy-set"})

    assert run.status_code == status.HTTP_201_CREATED, run.text
    assert run.json()["data"]["summary_json"]["passed"] == 1


@pytest.mark.asyncio
async def test_a_viewer_reads_datasets_but_cannot_change_anything(async_client) -> None:
    agent_id = await _agent(async_client)
    dataset = await _dataset(async_client, agent_id)
    url = f"{BASE}/datasets/{dataset['id']}"
    case = (await async_client.post(f"{url}/cases", json=_case("one"))).json()["data"]
    viewer = RequestContext(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="viewer-user",
        workspace_role="Viewer",
        tenant_role="Viewer",
    )

    with _as_context(viewer):
        for path in (
            "/datasets",
            f"/datasets/{dataset['id']}",
            f"/datasets/{dataset['id']}/cases",
            f"/datasets/{dataset['id']}/cases/{case['id']}",
            f"/datasets/{dataset['id']}/versions",
            f"/datasets/{dataset['id']}/export",
            "/reports",
        ):
            response = await async_client.get(f"{BASE}{path}")
            assert response.status_code == status.HTTP_200_OK, path

        writes = [
            ("post", "/datasets", {"subject_id": agent_id, "name": "viewer"}),
            ("patch", f"/datasets/{dataset['id']}", {"description": "no"}),
            ("delete", f"/datasets/{dataset['id']}", None),
            ("post", f"/datasets/{dataset['id']}/cases", _case("viewer")),
            ("patch", f"/datasets/{dataset['id']}/cases/{case['id']}", {"name": "no"}),
            ("delete", f"/datasets/{dataset['id']}/cases/{case['id']}", None),
            ("post", f"/datasets/{dataset['id']}/import", {"content": json.dumps(_case("viewer"))}),
        ]
        for method, path, body in writes:
            kwargs = {"json": body} if body is not None else {}
            response = await async_client.request(method, f"{BASE}{path}", **kwargs)
            assert response.status_code == status.HTTP_403_FORBIDDEN, (method, path, response.text)

    after = (await async_client.get(url)).json()["data"]
    assert (after["revision"], after["case_count"], after["status"]) == (2, 1, "active")


@pytest.mark.asyncio
async def test_another_tenant_cannot_see_or_change_a_dataset(
    async_client, async_db, tenant1_ctx, tenant2_ctx
) -> None:
    owned = RegressionDatasetService(db=async_db, ctx=tenant1_ctx)
    dataset = await owned.create_dataset(subject_kind="agent", subject_id="agt_t1", name="private")
    case = await owned.add_case(dataset.id, _case("secret"))
    await owned.export_cases(dataset.id)
    url = f"{BASE}/datasets/{dataset.id}"

    with _as_context(tenant1_ctx):
        mine = await async_client.get(f"{BASE}/datasets")
        assert [item["id"] for item in mine.json()["data"]] == [dataset.id]

    with _as_context(tenant2_ctx):
        assert (await async_client.get(f"{BASE}/datasets")).json()["data"] == []
        for method, path, body in [
            ("get", "", None),
            ("patch", "", {"description": "x"}),
            ("delete", "", None),
            ("get", "/cases", None),
            ("post", "/cases", _case("x")),
            ("get", f"/cases/{case.id}", None),
            ("patch", f"/cases/{case.id}", {"name": "x"}),
            ("delete", f"/cases/{case.id}", None),
            ("post", "/import", {"content": json.dumps(_case("x"))}),
            ("get", "/export", None),
            ("get", "/versions", None),
            ("get", "/versions/1", None),
        ]:
            kwargs = {"json": body} if body is not None else {}
            response = await async_client.request(method, f"{url}{path}", **kwargs)
            assert response.status_code == status.HTTP_404_NOT_FOUND, (method, path, response.text)

    with _as_context(tenant1_ctx):
        untouched = (await async_client.get(url)).json()["data"]
    assert (untouched["revision"], untouched["case_count"], untouched["description"]) == (2, 1, "")
