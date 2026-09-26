"""Budgets are kept by workspace admins and stop spend at the gateway."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.main import app
from app.middleware.auth import get_current_context

BASE = "/api/v1/billing/budgets"


async def _spend(async_db, ctx: RequestContext, amount: str) -> None:
    async_db.add(
        Run(
            id="run_spent",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            mode="gateway",
            status="succeeded",
        )
    )
    async_db.add(
        RunCostEntry(
            run_id="run_spent",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            billing_basis="tokens",
            billed_quantity=Decimal(1),
            currency="USD",
            amount=Decimal(amount),
        )
    )
    await async_db.commit()


@pytest.mark.asyncio
async def test_admins_keep_budgets_and_see_their_status(async_client, async_db, ctx) -> None:
    await _spend(async_db, ctx, "2.5")

    created = await async_client.post(
        BASE, json={"name": "Team monthly", "amount": "10", "currency": "USD"}
    )
    assert created.status_code == 201
    budget = created.json()["data"]
    assert (budget["period"], budget["hard_stop"], budget["thresholds"]) == ("month", True, [50, 80, 100])

    status = (await async_client.get(f"{BASE}/{budget['id']}/status")).json()["data"]
    assert Decimal(status["spent"]) == Decimal("2.5")
    assert Decimal(status["remaining"]) == Decimal("7.5")
    assert Decimal(status["percent"]) == Decimal("25")
    assert Decimal(status["forecast"]) >= Decimal("2.5")

    daily = await async_client.post(
        BASE, json={"name": "Agents daily", "amount": "5", "currency": "USD", "period": "day"}
    )
    overview = (await async_client.get(f"{BASE}/statuses")).json()["data"]
    assert [(item["budget"]["name"], Decimal(item["spent"])) for item in overview] == [
        ("Agents daily", Decimal("2.5")),
        ("Team monthly", Decimal("2.5")),
    ]
    assert (overview[1]["budget"]["id"], overview[1]["percent"]) == (budget["id"], status["percent"])
    assert (await async_client.delete(f"{BASE}/{daily.json()['data']['id']}")).status_code == 204

    changed = await async_client.patch(f"{BASE}/{budget['id']}", json={"amount": "20", "hard_stop": False})
    assert (Decimal(changed.json()["data"]["amount"]), changed.json()["data"]["hard_stop"]) == (20, False)
    assert [item["id"] for item in (await async_client.get(BASE)).json()["data"]] == [budget["id"]]
    assert (await async_client.delete(f"{BASE}/{budget['id']}")).status_code == 204


@pytest.mark.asyncio
async def test_budgets_are_governed_and_validated(async_client, ctx) -> None:
    missing_scope = await async_client.post(
        BASE, json={"name": "Key", "amount": "1", "currency": "USD", "scope_kind": "api_key"}
    )
    assert missing_scope.status_code == 400
    bad_currency = await async_client.post(BASE, json={"name": "X", "amount": "1", "currency": "usd"})
    assert bad_currency.status_code == 400

    developer = dataclasses.replace(ctx, workspace_role="Dev", tenant_role=None)
    app.dependency_overrides[get_current_context] = lambda: developer
    try:
        refused = await async_client.post(BASE, json={"name": "X", "amount": "1", "currency": "USD"})
        listed = await async_client.get(BASE)
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx
    assert refused.status_code == 403
    assert listed.status_code == 200


@pytest.mark.asyncio
async def test_a_spent_budget_stops_gateway_calls(async_client, async_db, ctx) -> None:
    await _spend(async_db, ctx, "5")
    await async_client.post(BASE, json={"name": "Hard cap", "amount": "5", "currency": "USD"})

    response = await async_client.post(
        "/v1/chat/completions",
        json={"model": "model:test:chat", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 402
    error = response.json()["error"]
    assert error["type"] == "insufficient_quota"
    assert error["code"] == "budget_exhausted"
    assert "Hard cap" in error["message"]
