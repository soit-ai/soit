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


@pytest.fixture
def key_counters(monkeypatch):
    """Rate windows kept in memory, so each test starts with fresh ones."""
    from app.kernel.commons.errors import RateLimitExceededError
    from app.kernel.ports.common.rate_limiter import RateLimiter

    spent: list[str] = []

    async def check_rate_limit(_self, key: str, limit: int, window_seconds: int) -> bool:
        spent.append(key)
        if spent.count(key) > limit:
            raise RateLimitExceededError(
                f"Rate limit exceeded: {limit} requests per {window_seconds} seconds",
                {"limit": limit, "window_seconds": window_seconds, "retry_after": 30},
            )
        return True

    monkeypatch.setattr(RateLimiter, "check_rate_limit", check_rate_limit)
    return spent


def _keyed(ctx, **limits):
    return dataclasses.replace(ctx, api_key_id="key_1", **limits)


def _key_spend(spent: list[str]) -> list[str]:
    return [key for key in spent if "api_key" in key]


RANDOM = "/api/v1/tools/tool:function:random_int/invoke"
ONE = {"arguments": {"min": 1, "max": 1}}


@pytest.mark.usefixtures("key_counters")
async def test_a_keys_rate_counts_its_tool_calls(async_client, async_db, ctx) -> None:
    _as(_keyed(ctx, api_key_rate_limit_per_minute=1))
    try:
        first = await async_client.post(RANDOM, json=ONE)
        second = await async_client.post(RANDOM, json=ONE)
    finally:
        _as(ctx)

    assert first.status_code == 200, first.text
    assert second.status_code == 429, second.text
    assert second.headers["retry-after"] == "30"
    assert second.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert second.json()["details"]["quota"] == "per_minute"
    # Refused before anything was recorded: one run, the first call's.
    runs = (await async_db.exec(select(Run).where(Run.mode == "tool"))).all()
    assert [run.id for run in runs] == [first.json()["data"]["run_id"]]


async def test_a_keys_daily_quota_counts_each_call_once(async_client, async_db, ctx, key_counters) -> None:
    _as(_keyed(ctx, api_key_daily_request_quota=1))
    try:
        first = await async_client.post(RANDOM, json=ONE, headers={"Idempotency-Key": "once"})
        replay = await async_client.post(RANDOM, json=ONE, headers={"Idempotency-Key": "once"})
        another = await async_client.post(RANDOM, json=ONE, headers={"Idempotency-Key": "another"})
    finally:
        _as(ctx)

    assert first.status_code == replay.status_code == 200
    assert replay.json()["data"]["replayed"] is True
    assert another.status_code == 429, another.text
    assert another.json()["details"]["quota"] == "daily_requests"
    assert _key_spend(key_counters) == ["quota:llm:api_key:key_1", "quota:llm:api_key:key_1"]
    refused = [
        run
        for run in (await async_db.exec(select(Run).where(Run.mode == "tool"))).all()
        if run.id != first.json()["data"]["run_id"]
    ]
    assert [(run.status, run.error_code, run.api_key_id) for run in refused] == [
        ("failed", "RATE_LIMIT_EXCEEDED", "key_1")
    ]
    calls = (await async_db.exec(select(RunStepToolCall).where(RunStepToolCall.run_id == refused[0].id))).all()
    costs = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == refused[0].id))).all()
    assert calls == [] and costs == []


async def test_a_call_the_key_refused_runs_when_sent_again(async_client, ctx, key_counters) -> None:
    # A refusal records no outcome under the idempotency key, so sending the
    # call again once the window moves runs it rather than replaying a failure.
    _as(_keyed(ctx, api_key_daily_request_quota=1, api_key_rate_limit_per_minute=10))
    headers = {"Idempotency-Key": "later"}
    try:
        await async_client.post(RANDOM, json=ONE)
        refused = await async_client.post(RANDOM, json=ONE, headers=headers)
        key_counters.clear()
        accepted = await async_client.post(RANDOM, json=ONE, headers=headers)
    finally:
        _as(ctx)

    assert refused.status_code == 429
    assert accepted.status_code == 200, accepted.text
    assert (accepted.json()["data"]["status"], accepted.json()["data"]["replayed"]) == ("succeeded", False)


@pytest.mark.usefixtures("key_counters")
async def test_an_approved_call_runs_without_spending_the_daily_quota_again(async_client, ctx) -> None:
    _register_gated_tool(ctx)
    call = {"arguments": {"min": 5, "max": 5}}
    _as(_keyed(ctx, api_key_daily_request_quota=1))
    try:
        waiting = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call)
        key = {"Idempotency-Key": waiting.json()["data"]["idempotency_key"]}
        polled = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
        await async_client.post(
            f"/api/v1/observe/approvals/{waiting.json()['data']['approval_id']}/resolve",
            json={"status": "approved"},
        )
        done = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
        fresh = await async_client.post(RANDOM, json=ONE)
    finally:
        _as(ctx)

    assert (waiting.status_code, polled.status_code) == (202, 202)
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "succeeded"
    assert fresh.status_code == 429, "the approved call's quota was spent when it was made"


async def test_an_approved_call_refused_by_the_rate_still_runs_when_sent_again(
    async_client, ctx, key_counters
) -> None:
    # The rate is spent before anything changes, so a refusal cannot void the approval.
    _register_gated_tool(ctx)
    call = {"arguments": {"min": 5, "max": 5}}
    _as(_keyed(ctx, api_key_rate_limit_per_minute=1))
    try:
        waiting = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call)
        key = {"Idempotency-Key": waiting.json()["data"]["idempotency_key"]}
        await async_client.post(
            f"/api/v1/observe/approvals/{waiting.json()['data']['approval_id']}/resolve",
            json={"status": "approved"},
        )
        refused = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
        key_counters.clear()
        done = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json=call, headers=key)
    finally:
        _as(ctx)

    assert refused.status_code == 429
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "succeeded"


@pytest.mark.usefixtures("key_counters")
async def test_a_gated_call_the_key_refused_opens_no_approval(async_client, async_db, ctx) -> None:
    from app.modules.observe.domain.models import ApprovalRequest

    _register_gated_tool(ctx)
    _as(_keyed(ctx, api_key_daily_request_quota=1))
    try:
        await async_client.post(RANDOM, json=ONE)
        refused = await async_client.post(f"/api/v1/tools/{GATED}/invoke", json={"arguments": {"min": 5, "max": 5}})
    finally:
        _as(ctx)

    assert refused.status_code == 429
    assert (await async_db.exec(select(ApprovalRequest))).all() == []
    gated = (await async_db.exec(select(RunStepToolCall).where(RunStepToolCall.tool_ref == GATED))).all()
    assert gated == []


async def test_a_refused_tool_or_one_outside_the_keys_list_spends_nothing(async_client, ctx, key_counters) -> None:
    limited = _keyed(
        ctx,
        api_key_rate_limit_per_minute=5,
        api_key_daily_request_quota=5,
        allowed_tools=frozenset({"tool:function:time_now"}),
    )
    _as(limited)
    try:
        outside = await async_client.post(RANDOM, json=ONE)
        unknown = await async_client.post("/api/v1/tools/tool:none:such/invoke", json={"arguments": {}})
        listed = await async_client.get("/api/v1/tools")
    finally:
        _as(ctx)

    assert (outside.status_code, unknown.status_code, listed.status_code) == (403, 403, 200)
    assert _key_spend(key_counters) == []


async def test_a_session_without_a_key_spends_no_key_budget(async_client, ctx, key_counters) -> None:
    _as(dataclasses.replace(ctx, api_key_rate_limit_per_minute=1, api_key_daily_request_quota=1))
    try:
        first = await async_client.post(RANDOM, json=ONE)
        second = await async_client.post(RANDOM, json=ONE)
    finally:
        _as(ctx)

    assert first.status_code == second.status_code == 200
    assert _key_spend(key_counters) == []


@pytest.mark.usefixtures("key_counters")
async def test_a_tool_call_spends_the_budget_a_model_call_needs(async_client, ctx) -> None:
    _as(_keyed(ctx, api_key_rate_limit_per_minute=1))
    try:
        tool = await async_client.post(RANDOM, json=ONE)
        chat = await async_client.post(
            "/v1/chat/completions",
            json={"model": "model:test:chat", "messages": [{"role": "user", "content": "hi"}]},
        )
    finally:
        _as(ctx)

    assert tool.status_code == 200, tool.text
    assert chat.status_code == 429, chat.text
    assert chat.json()["error"]["code"] == "rate_limit_exceeded"
    assert chat.headers["retry-after"] == "30"


@pytest.mark.usefixtures("_tool_sessions_share_the_test_database")
async def test_a_tools_own_model_calls_spend_no_more_of_the_keys_limits(
    async_client, async_db, ctx, key_counters
) -> None:
    # knowledge_query embeds the query through the model gateway under the
    # caller's context; the direct call already spent the key's limits.
    from app.kernel.commons.time import utc_now
    from app.modules.knowledge.domain.models import KnowledgeIndex

    knowledge_id = await _create_knowledge(async_client, "keyed-query", "workspace")
    now = utc_now()
    async_db.add(
        KnowledgeIndex(
            id="idx_keyed_query",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            knowledge_id=knowledge_id,
            name="Primary Index",
            is_primary=True,
            provider="pgvector",
            embedding_model_ref="model:test:embedding",
            dimension=3,
            metric_type="cosine",
            status="ready",
            created_at=now,
            updated_at=now,
        )
    )
    await async_db.commit()
    _as(_keyed(ctx, api_key_rate_limit_per_minute=1, api_key_daily_request_quota=1))
    try:
        response = await async_client.post(
            KNOWLEDGE_QUERY, json={"arguments": {"knowledge_id": knowledge_id, "query": "refunds"}}
        )
    finally:
        _as(ctx)

    assert response.status_code == 200, response.text
    assert "Rate limit" not in (response.json()["data"]["error"] or ""), response.json()["data"]["error"]
    assert _key_spend(key_counters) == ["llm:api_key:key_1", "quota:llm:api_key:key_1"]


async def test_a_request_for_a_call_still_running_does_not_run_it_again(async_client, async_db, ctx) -> None:
    # The caller chooses X-Request-Id; a repeated request under the same one
    # must not find the running call's lease to be its own.
    from datetime import timedelta

    from app.kernel.commons.time import utc_now

    same_request = dataclasses.replace(ctx, request_id="req-chosen-by-caller")
    headers = {"Idempotency-Key": "in-flight"}
    _as(same_request)
    try:
        first = await async_client.post(RANDOM, json=ONE, headers=headers)
        [record] = (
            await async_db.exec(
                select(RunStepToolCall).where(RunStepToolCall.run_id == first.json()["data"]["run_id"])
            )
        ).all()
        # As if the first request were still running the tool under that id.
        record.status = "running"
        record.lease_owner = "req-chosen-by-caller"
        record.lease_expires_at = utc_now() + timedelta(minutes=5)
        async_db.add(record)
        await async_db.commit()
        again = await async_client.post(RANDOM, json=ONE, headers=headers)
    finally:
        _as(ctx)

    assert again.status_code == 409, again.text
    costs = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == record.run_id))).all()
    assert len(costs) == 1
