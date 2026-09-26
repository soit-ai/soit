"""Tools are invoked by reference, each call a governed run of its own."""

from __future__ import annotations

import dataclasses

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
