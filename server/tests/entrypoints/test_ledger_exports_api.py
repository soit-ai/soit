"""Ledger exports stream the workspace's records in the contract, and are audited."""

from __future__ import annotations

import csv
import dataclasses
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs.ledger import LEDGER_SPEC
from app.kernel.runtime.runs.ledger_export import csv_columns, iter_ledger_records
from app.kernel.specs import validate_spec
from app.main import app
from app.middleware.auth import get_current_context

pytestmark = pytest.mark.asyncio

T0 = datetime(2026, 9, 20, 8, 0, 0)
WINDOW = {"since": "2026-09-20T00:00:00Z", "until": "2026-09-21T00:00:00Z"}


def _run(ctx: RequestContext, run_id: str, at: datetime, workspace_id: str | None = None) -> Run:
    return Run(
        id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=workspace_id or ctx.workspace_id,
        user_id=ctx.user_id,
        mode="agent",
        status="succeeded",
        started_at=at,
        created_at=at,
        updated_at=at,
    )


async def _seed(async_db, ctx: RequestContext) -> None:
    async_db.add_all(
        [
            _run(ctx, "run_b", T0 + timedelta(hours=2)),
            _run(ctx, "run_a", T0),
            _run(ctx, "run_old", T0 - timedelta(days=3)),
            _run(ctx, "run_elsewhere", T0, workspace_id="another-workspace"),
            RunStep(
                id="step_1",
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                run_id="run_a",
                step_type="llm",
                status="succeeded",
                metrics_json={"model_ref": "model:test:chat"},
                started_at=T0,
                created_at=T0,
            ),
            RunCostEntry(
                id="ce_1",
                run_id="run_a",
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                currency="USD",
                amount=Decimal("0.25"),
                billing_basis="tokens",
                billed_quantity=Decimal("100"),
                created_at=T0,
            ),
            AuditEvent(
                id="aud_1",
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                event_type="policy.egress.updated",
                resource_type="egress",
                operation="update",
                actor_user_id=ctx.user_id,
                payload_json={"allowlist": ["docs.acme.io"]},
                created_at=T0,
            ),
            EventOutbox(
                id="obx_1",
                event_id="evt_1",
                event_type="run.created",
                idempotency_key="evt_1",
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                run_id="run_a",
                payload_json={"run_id": "run_a"},
                status="processed",
                occurred_at=T0,
                created_at=T0,
                lock_owner="worker-7",
            ),
        ]
    )
    await async_db.commit()


def _lines(body: str) -> list[dict]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


async def test_each_kind_exports_the_windows_records_in_the_contract(async_client, async_db, ctx) -> None:
    await _seed(async_db, ctx)

    runs = await async_client.get("/api/v1/exports/runs", params=WINDOW)
    assert runs.status_code == 200, runs.text
    assert runs.headers["content-type"].startswith("application/x-ndjson")
    assert runs.headers["x-soit-ledger-schema"] == "1.0"
    assert "soit-runs-20260920T000000Z-20260921T000000Z.jsonl" in runs.headers["content-disposition"]
    documents = _lines(runs.text)
    # In the window, in this workspace, oldest first.
    assert [doc["record"]["run_id"] for doc in documents] == ["run_a", "run_b"]

    for kind, record_id in (
        ("steps", "step_record_id"),
        ("costs", "cost_entry_id"),
        ("events", "outbox_id"),
    ):
        response = await async_client.get(f"/api/v1/exports/{kind}", params=WINDOW)
        assert response.status_code == 200, response.text
        exported = _lines(response.text)
        assert len(exported) == 1
        documents.extend(exported)
        assert exported[0]["record"][record_id]

    audit = _lines((await async_client.get("/api/v1/exports/audit", params=WINDOW)).text)
    assert [doc["record"]["audit_id"] for doc in audit] == ["aud_1"]
    documents.extend(audit)

    for document in documents:
        assert validate_spec(document, LEDGER_SPEC) is True
    # Delivery state stays inside.
    event = next(doc for doc in documents if doc["record_type"] == "event")
    assert "lock_owner" not in event["record"]


async def test_csv_follows_the_contract_columns(async_client, async_db, ctx) -> None:
    await _seed(async_db, ctx)

    response = await async_client.get("/api/v1/exports/costs", params={**WINDOW, "format": "csv"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == csv_columns("costs")
    record = dict(zip(rows[0], rows[1], strict=True))
    assert (record["cost_entry_id"], record["amount"], record["billed_quantity"]) == ("ce_1", "0.25", "100")
    assert json.loads(record["pricing_snapshot"]) == {}
    assert record["step_id"] == ""


async def test_batches_neither_skip_nor_repeat_records(async_db, ctx) -> None:
    same = T0 + timedelta(minutes=5)
    async_db.add_all([_run(ctx, f"run_{index}", same if index % 2 else T0) for index in range(7)])
    await async_db.commit()

    exported = [
        document["record"]["run_id"]
        async for document in iter_ledger_records(
            async_db, ctx, "runs", since=T0, until=T0 + timedelta(hours=1), batch_size=2
        )
    ]

    assert sorted(exported) == sorted(f"run_{index}" for index in range(7))
    assert len(exported) == len(set(exported))


async def test_exporting_takes_governance_and_is_audited(async_client, async_db, ctx) -> None:
    developer = dataclasses.replace(ctx, workspace_role="Dev", tenant_role=None)
    app.dependency_overrides[get_current_context] = lambda: developer
    try:
        refused = await async_client.get("/api/v1/exports/runs", params=WINDOW)
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx
    assert refused.status_code == 403

    backwards = await async_client.get(
        "/api/v1/exports/runs", params={"since": WINDOW["until"], "until": WINDOW["since"]}
    )
    too_long = await async_client.get(
        "/api/v1/exports/runs", params={"since": "2026-01-01T00:00:00Z", "until": "2026-09-01T00:00:00Z"}
    )
    assert (backwards.status_code, too_long.status_code) == (400, 400)

    ok = await async_client.get("/api/v1/exports/audit", params={**WINDOW, "format": "csv"})
    assert ok.status_code == 200
    recorded = (
        await async_db.exec(select(AuditEvent).where(AuditEvent.event_type == "ledger.exported"))
    ).all()
    assert [(event.resource_id, event.actor_user_id, event.payload_json["format"]) for event in recorded] == [
        ("audit", ctx.user_id, "csv")
    ]


async def test_a_browser_can_read_the_download_name_across_origins(async_client) -> None:
    from app.main import cors_origins

    origin = next((item for item in cors_origins if item != "*"), "http://localhost:5000")
    response = await async_client.get("/api/v1/exports/runs", params=WINDOW, headers={"Origin": origin})

    exposed = {name.strip().lower() for name in response.headers.get("access-control-expose-headers", "").split(",")}
    assert {"content-disposition", "x-soit-ledger-schema"} <= exposed
