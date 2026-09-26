"""Entrypoint tests for the workspace credit ledger API."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi import status

from app.kernel.contracts.context import RequestContext
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.billing.domain.models import CreditLedgerEntry
from app.settings.settings import settings

pytestmark = pytest.mark.asyncio


def _as_role(ctx: RequestContext, role: str) -> None:
    scoped = replace(ctx, workspace_role=role, tenant_role="Member")

    async def _override() -> RequestContext:
        return scoped

    app.dependency_overrides[get_current_context] = _override


async def test_grant_then_balance_reflects_the_ledger(async_client, ctx) -> None:
    grant = await async_client.post(
        "/api/v1/billing/credits/grants", json={"credits": "500", "note": "starter credits"}
    )
    assert grant.status_code == status.HTTP_201_CREATED
    body = grant.json()["data"]
    assert body["kind"] == "grant"
    assert Decimal(str(body["credits_delta"])) == Decimal("500")
    assert body["created_by"] == ctx.user_id

    balance = await async_client.get("/api/v1/billing/credits/balance")
    assert balance.status_code == status.HTTP_200_OK
    data = balance.json()["data"]
    assert Decimal(str(data["balance"])) == Decimal("500")
    assert Decimal(str(data["granted_total"])) == Decimal("500")
    assert data["entry_count"] == 1
    assert data["status"] == "ok"
    assert data["enforcement_enabled"] is settings.credit_enforcement_enabled


async def test_entries_filter_by_kind_and_run(async_client, async_db, ctx) -> None:
    async_db.add_all(
        [
            CreditLedgerEntry(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                kind="grant",
                credits_delta=Decimal("100"),
                created_by=ctx.user_id,
            ),
            CreditLedgerEntry(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                kind="deduction",
                credits_delta=Decimal("-7"),
                cost_entry_id="cost_api_1",
                run_id="run_api_1",
                currency="USD",
                amount=Decimal("0.007"),
                created_by="system:credit-deduction",
            ),
            CreditLedgerEntry(
                tenant_id="other-tenant",
                workspace_id="other-workspace",
                kind="grant",
                credits_delta=Decimal("999"),
                created_by="someone-else",
            ),
        ]
    )
    await async_db.flush()

    listed = await async_client.get("/api/v1/billing/credits/entries")
    assert listed.status_code == status.HTTP_200_OK
    assert {row["kind"] for row in listed.json()["data"]} == {"grant", "deduction"}

    deductions = await async_client.get("/api/v1/billing/credits/entries?kind=deduction")
    assert [row["cost_entry_id"] for row in deductions.json()["data"]] == ["cost_api_1"]

    by_run = await async_client.get("/api/v1/billing/credits/entries?run_id=run_api_1")
    assert [row["run_id"] for row in by_run.json()["data"]] == ["run_api_1"]

    balance = await async_client.get("/api/v1/billing/credits/balance")
    assert Decimal(str(balance.json()["data"]["balance"])) == Decimal("93")


async def test_non_positive_grant_is_rejected(async_client) -> None:
    response = await async_client.post("/api/v1/billing/credits/grants", json={"credits": "0"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize("role", ["Admin", "Dev", "Viewer"])
async def test_only_the_workspace_owner_may_grant(async_client, ctx, role: str) -> None:
    _as_role(ctx, role)

    response = await async_client.post("/api/v1/billing/credits/grants", json={"credits": "10"})

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_a_viewer_can_read_the_balance(async_client, ctx) -> None:
    _as_role(ctx, "Viewer")

    response = await async_client.get("/api/v1/billing/credits/balance")

    assert response.status_code == status.HTTP_200_OK
