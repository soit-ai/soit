"""Each run carries the cost of its own priced ledger entries.

The console lists an agent's or workflow's runs with a cost column, which the
``/runs/costs/*`` aggregates cannot fill row by row. These assertions lock the
two fields the run record answers that with, on the list and detail endpoints.
"""

from decimal import Decimal

import pytest
from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run, RunCostEntry

pytestmark = pytest.mark.asyncio


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def _run(run_id: str) -> Run:
    return Run(
        id=run_id,
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agt_cost",
        subject_version_id="agtv_cost",
        status="succeeded",
        started_at=utc_now(),
    )


def _entry(run_id: str, amount: str | None, currency: str | None, tokens: int = 10) -> RunCostEntry:
    return RunCostEntry(
        run_id=run_id,
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        billing_basis="tokens",
        billed_quantity=Decimal(tokens),
        currency=currency,
        amount=Decimal(amount) if amount is not None else None,
        prompt_tokens=tokens,
        total_tokens=tokens,
    )


async def _seed(async_db) -> None:
    async_db.add(_run("run_cost_priced"))
    async_db.add(_entry("run_cost_priced", "0.25", "USD"))
    async_db.add(_entry("run_cost_priced", "0.5", "USD"))
    async_db.add(_entry("run_cost_priced", None, None))
    async_db.add(_run("run_cost_unpriced"))
    async_db.add(_entry("run_cost_unpriced", None, None))
    async_db.add(_run("run_cost_none"))
    async_db.add(_run("run_cost_mixed"))
    async_db.add(_entry("run_cost_mixed", "1", "USD"))
    async_db.add(_entry("run_cost_mixed", "2", "EUR"))
    # Another workspace's entry against the same run id must not leak in.
    async_db.add(
        RunCostEntry(
            run_id="run_cost_none",
            tenant_id="test-tenant",
            workspace_id="other-workspace",
            billing_basis="tokens",
            billed_quantity=Decimal(1),
            currency="USD",
            amount=Decimal("9"),
        )
    )
    await async_db.commit()


async def test_run_list_carries_each_runs_priced_total(async_client, async_db):
    await _seed(async_db)

    response = await async_client.get("/api/v1/runs", params={"page_size": 10}, headers=_headers())
    assert response.status_code == status.HTTP_200_OK
    by_id = {item["id"]: item for item in response.json()["data"]["items"]}

    assert Decimal(by_id["run_cost_priced"]["cost_amount"]) == Decimal("0.75")
    assert by_id["run_cost_priced"]["cost_currency"] == "USD"
    for run_id in ("run_cost_unpriced", "run_cost_none", "run_cost_mixed"):
        assert by_id[run_id]["cost_amount"] is None, run_id
        assert by_id[run_id]["cost_currency"] is None, run_id


@pytest.mark.parametrize("include_cost", ["true", "false"])
async def test_run_detail_carries_the_priced_total(async_client, async_db, include_cost):
    await _seed(async_db)

    priced = await async_client.get(
        "/api/v1/runs/run_cost_priced", params={"include_cost": include_cost}, headers=_headers()
    )
    assert priced.status_code == status.HTTP_200_OK
    run = priced.json()["data"]["run"]
    assert (Decimal(run["cost_amount"]), run["cost_currency"]) == (Decimal("0.75"), "USD")

    for run_id in ("run_cost_none", "run_cost_mixed"):
        response = await async_client.get(
            f"/api/v1/runs/{run_id}", params={"include_cost": include_cost}, headers=_headers()
        )
        assert response.status_code == status.HTTP_200_OK
        run = response.json()["data"]["run"]
        assert (run["cost_amount"], run["cost_currency"]) == (None, None), run_id
