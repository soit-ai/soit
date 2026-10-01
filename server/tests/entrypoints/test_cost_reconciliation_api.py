"""Cost entries filtered for a bill check, and the ledger's side of that check.

``/runs/costs/entries`` narrows by the run's key, principal and source and by
the entry's model, tool, currency and pricing status; ``/runs/costs/reconciliation``
totals the same entries per currency, counts them per pricing status, says why
unpriced ones went unpriced, and groups them by a dimension.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run, RunCostEntry

pytestmark = pytest.mark.asyncio

T0 = utc_now().replace(microsecond=0) - timedelta(hours=1)


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def _run(run_id: str, *, api_key_id: str | None, user_id: str, source: str) -> Run:
    return Run(
        id=run_id,
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id=user_id,
        api_key_id=api_key_id,
        source=source,
        mode="agent",
        kind="agent",
        status="succeeded",
        started_at=T0,
    )


def _entry(
    run_id: str,
    minute: int,
    amount: str | None,
    currency: str | None,
    *,
    model_ref: str | None = "model:openai:gpt-5.1",
    tool_ref: str | None = None,
    snapshot: dict | None = None,
    tokens: int = 10,
    workspace_id: str = "test-workspace",
) -> RunCostEntry:
    return RunCostEntry(
        run_id=run_id,
        tenant_id="test-tenant",
        workspace_id=workspace_id,
        billing_basis="tokens",
        billed_quantity=Decimal(tokens),
        currency=currency,
        amount=Decimal(amount) if amount is not None else None,
        pricing_snapshot_json=snapshot or {"priced": amount is not None},
        model_ref=model_ref,
        provider_slug=model_ref.split(":")[1] if model_ref else None,
        tool_ref=tool_ref,
        total_tokens=tokens,
        created_at=T0 + timedelta(minutes=minute),
    )


async def _seed(async_db) -> None:
    async_db.add(_run("run_gw_a", api_key_id="key_a", user_id="u_alice", source="gateway"))
    async_db.add(_run("run_gw_b", api_key_id="key_b", user_id="sp_bot", source="gateway"))
    async_db.add(_run("run_platform", api_key_id=None, user_id="u_alice", source="platform"))
    entries = [
        _entry("run_gw_a", 1, "0.40", "USD"),
        _entry("run_gw_a", 2, "0.10", "USD", snapshot={"priced": True, "usage_estimated": True}),
        _entry("run_gw_a", 3, None, None, model_ref="model:deepseek:chat", snapshot={"priced": False, "reason": "pricing_not_configured"}),
        _entry("run_gw_b", 4, "2.00", "CNY", model_ref="model:deepseek:chat"),
        _entry("run_gw_b", 5, None, None, model_ref="model:deepseek:chat", snapshot={"priced": False, "reason": "pricing_not_configured"}),
        _entry("run_platform", 6, "0", "USD", model_ref=None, tool_ref="tool:time:now"),
        _entry("run_platform", 7, None, None, model_ref=None, tool_ref="tool:search:web", snapshot={"priced": False, "reason": "tool_pricing_not_declared"}),
        # Another workspace's entry must never be counted.
        _entry("run_gw_a", 8, "9", "USD", workspace_id="other-workspace"),
    ]
    for entry in entries:
        async_db.add(entry)
    await async_db.commit()


async def _entries(async_client, **params) -> list[dict]:
    resp = await async_client.get("/api/v1/runs/costs/entries", params=params, headers=_headers())
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return resp.json()["data"]["items"]


async def _reconcile(async_client, **params) -> dict:
    resp = await async_client.get("/api/v1/runs/costs/reconciliation", params=params, headers=_headers())
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return resp.json()["data"]


async def test_entries_carry_the_runs_key_principal_and_pricing_status(async_client, async_db):
    await _seed(async_db)

    items = await _entries(async_client)

    assert len(items) == 7
    first = items[0]
    assert (first["api_key_id"], first["user_id"], first["run_source"]) == ("key_a", "u_alice", "gateway")
    assert [item["pricing_status"] for item in items] == [
        "priced",
        "estimated",
        "unpriced",
        "priced",
        "unpriced",
        "free",
        "unpriced",
    ]
    assert items[2]["unpriced_reason"] == "pricing_not_configured"
    assert items[0]["unpriced_reason"] is None


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"api_key_id": "key_b"}, 2),
        ({"user_id": "u_alice"}, 5),
        ({"source": "platform"}, 2),
        ({"model_ref": "model:deepseek:chat"}, 3),
        ({"provider_slug": "openai"}, 2),
        ({"tool_ref": "tool:search:web"}, 1),
        ({"currency": "USD"}, 3),
        ({"pricing_status": "unpriced"}, 3),
        ({"pricing_status": "estimated"}, 1),
        ({"pricing_status": "free"}, 1),
        ({"pricing_status": "priced"}, 2),
        ({"api_key_id": "key_a", "pricing_status": "priced"}, 1),
    ],
)
async def test_entries_filter(async_client, async_db, params, expected):
    await _seed(async_db)

    assert len(await _entries(async_client, **params)) == expected


async def test_reconciliation_keeps_currencies_apart_and_counts_statuses(async_client, async_db):
    await _seed(async_db)

    data = await _reconcile(async_client)

    assert data["entry_count"] == 7
    assert data["status_counts"] == {"priced": 2, "free": 1, "estimated": 1, "unpriced": 3}
    assert {code: Decimal(value) for code, value in data["amounts"].items()} == {
        "USD": Decimal("0.5"),
        "CNY": Decimal("2"),
    }
    assert {code: Decimal(value) for code, value in data["estimated_amounts"].items()} == {"USD": Decimal("0.1")}
    assert data["unpriced_reasons"] == [
        {"reason": "pricing_not_configured", "entry_count": 2},
        {"reason": "tool_pricing_not_declared", "entry_count": 1},
    ]
    assert data["external_reconciliation"] == "not_performed"


async def test_reconciliation_window_is_half_open(async_client, async_db):
    await _seed(async_db)

    data = await _reconcile(
        async_client,
        since=(T0 + timedelta(minutes=2)).isoformat(),
        until=(T0 + timedelta(minutes=4)).isoformat(),
    )

    # Minutes 2 and 3; the entry at minute 4 belongs to the next window.
    assert data["entry_count"] == 2
    assert data["status_counts"]["estimated"] == 1
    assert data["status_counts"]["unpriced"] == 1


async def test_reconciliation_groups_by_api_key_with_unpriced_rows_apart(async_client, async_db):
    await _seed(async_db)

    data = await _reconcile(async_client, group_by="api_key", source="gateway")

    rows = {(row["key"], row["currency"]): row for row in data["groups"]}
    assert set(rows) == {("key_a", "USD"), ("key_a", None), ("key_b", "CNY"), ("key_b", None)}
    assert Decimal(rows[("key_a", "USD")]["amount"]) == Decimal("0.5")
    assert rows[("key_a", "USD")]["estimated_count"] == 1
    assert rows[("key_a", None)]["amount"] is None
    assert rows[("key_a", None)]["unpriced_count"] == 1
    assert data["groups_truncated"] is False


async def test_reconciliation_groups_by_tool(async_client, async_db):
    await _seed(async_db)

    data = await _reconcile(async_client, group_by="tool", source="platform")

    assert [(row["key"], row["currency"], row["entry_count"]) for row in data["groups"]] == [
        ("tool:search:web", None, 1),
        ("tool:time:now", "USD", 1),
    ]


async def test_reconciliation_refuses_an_unknown_grouping(async_client):
    resp = await async_client.get(
        "/api/v1/runs/costs/reconciliation", params={"group_by": "planet"}, headers=_headers()
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST

