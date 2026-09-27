"""Tools are invoked by reference, each call a governed run of its own."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest
from sqlmodel import select

from app.kernel.registry.deps import get_registry
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStepToolCall
from app.main import app
from app.middleware.auth import get_current_context

pytestmark = pytest.mark.asyncio

GATED = "tool:function:gated_random"


@pytest.fixture(autouse=True)
def _kernel_lookups() -> None:
    # The API builds the container at startup; the ASGI test transport runs no lifespan.
    from app.wiring import get_container

    get_container()


def _register_gated_tool(ctx) -> None:
    get_registry().register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=GATED,
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "gated_random",
                "description": "A random integer, once someone has approved it",
                "adapter": "function",
                "input_schema": {
                    "type": "object",
                    "properties": {"min": {"type": "integer"}, "max": {"type": "integer"}},
                    "required": ["min", "max"],
                },
                "output_schema": {"type": "object"},
                "policy": {"approval": {"mode": "required", "risk_level": "high"}},
                "function": {"entrypoint": "app.utils.builtin_tools:random_int"},
            }
        },
    )


def _as(ctx):
    app.dependency_overrides[get_current_context] = lambda: ctx


async def _run(async_db, run_id: str) -> Run:
    run = await async_db.get(Run, run_id)
    await async_db.refresh(run)
    return run


async def test_the_catalog_lists_the_workspace_tools_and_their_gates(async_client, ctx) -> None:
    _register_gated_tool(ctx)

    response = await async_client.get("/api/v1/tools")

    assert response.status_code == 200, response.text
    tools = {item["ref"]: item for item in response.json()["data"]}
    assert {"tool:function:time_now", "tool:http:request", GATED} <= set(tools)
    assert tools[GATED]["approval_required"] is True
    assert tools[GATED]["risk_level"] == "high"
    assert tools["tool:function:random_int"]["input_schema"]["required"] == ["min", "max"]
    assert tools["tool:function:time_now"]["source_kind"] == "builtin"

    detail = await async_client.get(f"/api/v1/tools/{GATED}")
    assert detail.status_code == 200
    assert detail.json()["data"]["description"] == "A random integer, once someone has approved it"


async def test_a_call_runs_the_tool_as_a_governed_run(async_client, async_db) -> None:
    response = await async_client.post(
        "/api/v1/tools/tool:function:random_int/invoke",
        json={"arguments": {"min": 7, "max": 7}},
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert (body["status"], body["result"], body["replayed"]) == ("succeeded", {"value": 7}, False)
    assert response.headers["x-soit-run-id"] == body["run_id"]
    assert response.headers["idempotency-key"] == body["idempotency_key"]
    run = await _run(async_db, body["run_id"])
    assert (run.mode, run.kind, run.source, run.status) == ("tool", "tool", "gateway", "succeeded")
    calls = (await async_db.exec(select(RunStepToolCall).where(RunStepToolCall.run_id == run.id))).all()
    assert [(call.tool_ref, call.status) for call in calls] == [("tool:function:random_int", "succeeded")]
    costs = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run.id))).all()
    assert [(cost.tool_ref, cost.billing_basis) for cost in costs] == [("tool:function:random_int", "requests")]
    audits = (await async_db.exec(select(AuditEvent).where(AuditEvent.run_id == run.id))).all()
    assert audits, "the gateway writes the call to the audit ledger"


async def test_the_same_key_returns_the_recorded_outcome_without_calling_again(async_client, async_db) -> None:
    call = {"arguments": {"min": 1, "max": 1_000_000_000}}
    headers = {"Idempotency-Key": "order-42"}

    first = await async_client.post("/api/v1/tools/tool:function:random_int/invoke", json=call, headers=headers)
    second = await async_client.post("/api/v1/tools/tool:function:random_int/invoke", json=call, headers=headers)

    assert first.status_code == second.status_code == 200, second.text
    first_body, second_body = first.json()["data"], second.json()["data"]
    assert second_body["result"] == first_body["result"]
    assert second_body["run_id"] == first_body["run_id"]
    assert (first_body["replayed"], second_body["replayed"]) == (False, True)
    assert second_body["idempotency_key"] == "order-42"
    costs = (
        await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == first_body["run_id"]))
    ).all()
    assert len(costs) == 1

    other_arguments = await async_client.post(
        "/api/v1/tools/tool:function:random_int/invoke",
        json={"arguments": {"min": 2, "max": 3}},
        headers=headers,
    )
    assert other_arguments.status_code == 409
    other_tool = await async_client.post(
        "/api/v1/tools/tool:function:time_now/invoke", json={"arguments": {}}, headers=headers
    )
    assert other_tool.status_code == 409


async def test_keys_are_scoped_to_the_caller(async_client, ctx) -> None:
    call = {"arguments": {"min": 1, "max": 1_000_000_000}}
    headers = {"Idempotency-Key": "shared-key"}
    mine = await async_client.post("/api/v1/tools/tool:function:random_int/invoke", json=call, headers=headers)
    _as(dataclasses.replace(ctx, api_key_id="key_other"))
    try:
        theirs = await async_client.post(
            "/api/v1/tools/tool:function:random_int/invoke", json=call, headers=headers
        )
    finally:
        _as(ctx)

    assert theirs.status_code == 200
    assert theirs.json()["data"]["run_id"] != mine.json()["data"]["run_id"]
    assert theirs.json()["data"]["replayed"] is False


async def test_a_key_limited_to_other_tools_neither_sees_nor_calls_them(async_client, ctx) -> None:
    _as(dataclasses.replace(ctx, api_key_id="key_1", allowed_tools=frozenset({"tool:function:time_now"})))
    try:
        listed = await async_client.get("/api/v1/tools")
        refused = await async_client.post(
            "/api/v1/tools/tool:function:random_int/invoke", json={"arguments": {"min": 1, "max": 2}}
        )
        unknown = await async_client.post("/api/v1/tools/tool:none:such/invoke", json={"arguments": {}})
        allowed = await async_client.post("/api/v1/tools/tool:function:time_now/invoke", json={"arguments": {}})
    finally:
        _as(ctx)

    assert [item["ref"] for item in listed.json()["data"]] == ["tool:function:time_now"]
    assert refused.status_code == 403
    assert refused.json()["details"]["reason"] == "tool_not_allowed"
    # Not a 404: a limited key learns nothing about which other refs exist.
    assert unknown.status_code == 403
    assert allowed.status_code == 200


async def test_an_unknown_tool_is_not_found(async_client) -> None:
    response = await async_client.post("/api/v1/tools/tool:none:such/invoke", json={"arguments": {}})

    assert response.status_code == 404


async def test_invalid_arguments_are_refused_and_fail_the_run(async_client, async_db) -> None:
    response = await async_client.post(
        "/api/v1/tools/tool:function:random_int/invoke", json={"arguments": {"min": 1}}
    )

    assert response.status_code == 400
    runs = (await async_db.exec(select(Run).where(Run.mode == "tool"))).all()
    assert [(run.status, run.error_code) for run in runs] == [("failed", "VALIDATION_ERROR")]


async def test_a_gated_tool_waits_for_approval_then_runs_once_approved(async_client, async_db, ctx) -> None:
    _register_gated_tool(ctx)
    call = {"arguments": {"min": 5, "max": 5}}

    waiting = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call)

    assert waiting.status_code == 202, waiting.text
    body = waiting.json()["data"]
    assert body["status"] == "waiting_approval" and body["approval_id"]
    key = {"Idempotency-Key": body["idempotency_key"]}
    assert (await _run(async_db, body["run_id"])).status == "waiting_approval"

    still_waiting = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
    assert still_waiting.status_code == 202
    assert still_waiting.json()["data"]["approval_id"] == body["approval_id"]

    approval = await async_client.get(f"/api/v1/observe/approvals/{body['approval_id']}")
    assert approval.json()["data"]["run_id"] == body["run_id"]
    assert approval.json()["data"]["details_json"]["parameters"] == {"min": 5, "max": 5}
    resolved = await async_client.post(
        f"/api/v1/observe/approvals/{body['approval_id']}/resolve", json={"status": "approved"}
    )
    assert resolved.status_code == 200, resolved.text

    changed = await async_client.post(
        f"/api/v1/tools/{GATED}/invoke", json={"arguments": {"min": 6, "max": 6}}, headers=key
    )
    assert changed.status_code == 409, "only the arguments put up for approval can run"

    done = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
    assert done.status_code == 200, done.text
    assert (done.json()["data"]["status"], done.json()["data"]["result"]) == ("succeeded", {"value": 5})
    assert done.json()["data"]["run_id"] == body["run_id"]
    assert (await _run(async_db, body["run_id"])).status == "succeeded"

    again = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
    assert (again.status_code, again.json()["data"]["replayed"]) == (200, True)


async def test_a_rejected_call_is_reported_and_never_runs(async_client, async_db, ctx) -> None:
    _register_gated_tool(ctx)
    call = {"arguments": {"min": 5, "max": 5}}
    waiting = (await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call)).json()["data"]
    await async_client.post(
        f"/api/v1/observe/approvals/{waiting['approval_id']}/resolve",
        json={"status": "rejected", "resolution_note": "Not during the freeze"},
    )
    key = {"Idempotency-Key": waiting["idempotency_key"]}

    rejected = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
    again = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)

    assert rejected.status_code == 200
    assert (rejected.json()["data"]["status"], rejected.json()["data"]["result"]) == ("rejected", None)
    assert again.json()["data"]["status"] == "rejected"
    run = await _run(async_db, waiting["run_id"])
    assert (run.status, run.error_code, run.error_message) == (
        "canceled",
        "TOOL_APPROVAL_REJECTED",
        "Not during the freeze",
    )
    costs = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run.id))).all()
    assert costs == []


async def test_a_viewer_cannot_invoke(async_client, ctx) -> None:
    _as(dataclasses.replace(ctx, workspace_role="Viewer", tenant_role=None))
    try:
        listed = await async_client.get("/api/v1/tools")
        refused = await async_client.post(
            "/api/v1/tools/tool:function:time_now/invoke", json={"arguments": {}}
        )
    finally:
        _as(ctx)

    assert listed.status_code == 200
    assert refused.status_code == 403


KNOWLEDGE_QUERY = "/api/v1/tools/tool:function:knowledge_query/invoke"


@pytest.fixture
def _tool_sessions_share_the_test_database(async_db, monkeypatch) -> None:
    # knowledge_query opens a session of its own; bind it to the test engine.
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.modules.knowledge.runtime import tool_entrypoint

    monkeypatch.setattr(
        tool_entrypoint,
        "get_async_session_local",
        lambda: lambda: AsyncSession(async_db.bind, expire_on_commit=False),
    )


async def _create_knowledge(async_client, name: str, visibility: str) -> str:
    response = await async_client.post(
        "/api/v1/knowledge", json={"name": name, "knowledge_type": "document", "visibility": visibility}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


async def _knowledge_query_runs(async_db, knowledge_id: str) -> list[Run]:
    runs = (await async_db.exec(select(Run).where(Run.mode == "knowledge_query"))).all()
    return [run for run in runs if knowledge_id in (run.input_summary or "")]


@pytest.mark.usefixtures("_tool_sessions_share_the_test_database")
async def test_knowledge_query_runs_under_the_callers_own_roles(async_client, async_db, ctx) -> None:
    alice = dataclasses.replace(ctx, user_id="dev-alice", workspace_role="Dev", tenant_role="Member")
    bob = dataclasses.replace(ctx, user_id="dev-bob", workspace_role="Dev", tenant_role="Member")
    try:
        _as(alice)
        private_id = await _create_knowledge(async_client, "alice-private", "private")

        _as(bob)
        forged = await async_client.post(
            KNOWLEDGE_QUERY,
            json={"arguments": {"knowledge_id": private_id, "query": "x", "workspace_role": "Owner"}},
        )
        plain = await async_client.post(
            KNOWLEDGE_QUERY, json={"arguments": {"knowledge_id": private_id, "query": "x"}}
        )
        bob_runs = await _knowledge_query_runs(async_db, private_id)

        _as(alice)
        own = await async_client.post(
            KNOWLEDGE_QUERY, json={"arguments": {"knowledge_id": private_id, "query": "x"}}
        )
    finally:
        _as(ctx)

    # A role named in the arguments is refused outright.
    assert forged.status_code == 400, forged.text
    # Bob's own role cannot reach Alice's private knowledge base.
    assert plain.status_code == 200, plain.text
    assert plain.json()["data"]["status"] == "failed"
    assert "permission" in (plain.json()["data"]["error"] or "").lower(), plain.json()["data"]["error"]
    assert bob_runs == []
    # Alice's own roles let the call through to retrieval, where the new
    # knowledge base has nothing indexed yet.
    assert own.status_code == 200, own.text
    assert "no index" in (own.json()["data"]["error"] or ""), own.json()["data"]["error"]


@pytest.mark.usefixtures("_tool_sessions_share_the_test_database")
async def test_a_failed_knowledge_query_keeps_its_run(async_client, async_db) -> None:
    knowledge_id = await _create_knowledge(async_client, "no-index-yet", "workspace")

    response = await async_client.post(
        KNOWLEDGE_QUERY, json={"arguments": {"knowledge_id": knowledge_id, "query": "x"}}
    )

    assert response.json()["data"]["status"] == "failed"
    async_db.expire_all()
    runs = await _knowledge_query_runs(async_db, knowledge_id)
    # The tool's own session is never committed by its caller; the run is,
    # under the tool call's run.
    assert [(run.status, run.parent_run_id) for run in runs] == [("failed", response.json()["data"]["run_id"])]


PRICED = "tool:function:priced_random"


async def test_a_tool_that_declares_a_price_is_charged_it(async_client, async_db, ctx) -> None:
    get_registry().register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=PRICED,
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "priced_random",
                "adapter": "function",
                "input_schema": {
                    "type": "object",
                    "properties": {"min": {"type": "integer"}, "max": {"type": "integer"}},
                    "required": ["min", "max"],
                },
                "output_schema": {"type": "object"},
                "policy": {"audit_level": "basic", "pricing": {"currency": "USD", "call": "0.002"}},
                "function": {"entrypoint": "app.utils.builtin_tools:random_int"},
            }
        },
    )
    priced = await async_client.post(f"/api/v1/tools/{PRICED}/invoke", json={"arguments": {"min": 1, "max": 1}})
    unpriced = await async_client.post(
        "/api/v1/tools/tool:function:random_int/invoke", json={"arguments": {"min": 1, "max": 1}}
    )

    assert priced.status_code == unpriced.status_code == 200, priced.text
    [priced_cost] = (
        await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == priced.json()["data"]["run_id"]))
    ).all()
    assert (priced_cost.amount, priced_cost.currency) == (Decimal("0.002"), "USD")
    assert priced_cost.pricing_snapshot_json["source"] == "tool_spec"
    [unpriced_cost] = (
        await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == unpriced.json()["data"]["run_id"]))
    ).all()
    assert unpriced_cost.amount is None
    assert unpriced_cost.pricing_snapshot_json["reason"] == "tool_pricing_not_declared"
