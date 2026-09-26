"""A run's evidence leaves as one verifiable, reproducible bundle."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import zipfile
from decimal import Decimal

import pytest
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.responses import Response
from app.kernel.runtime.db.models.runs import RunCostEntry
from app.kernel.runtime.runs.ledger import LEDGER_SPEC
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.specs import validate_spec
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.identity.domain.models import Tenant, Workspace
from app.modules.observe.domain.models import ApprovalRequest

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _kernel_lookups() -> None:
    # The API builds the container at startup; the ASGI test transport runs no lifespan.
    from app.wiring import get_container

    get_container()

SNIPPET = "Refunds are issued within 14 days of the request."


async def _governed_run(async_db, ctx: RequestContext, capture: str = "full") -> str:
    async_db.add(Tenant(id=ctx.tenant_id, name="tenant"))
    async_db.add(
        Workspace(id=ctx.workspace_id, tenant_id=ctx.tenant_id, name="workspace", content_capture=capture)
    )
    await async_db.commit()

    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent", subject_kind="agent", subject_id="agt_refunds")
    step = await writer.create_step(run_id=run.id, step_type="llm", step_id="answer")
    await writer.update_step_status(step.id, "running")
    await writer.update_step_status(
        step.id,
        "succeeded",
        metrics={
            "model_ref": "model:test:chat",
            "content_safety": [
                {"direction": "inbound", "decision": "redact", "categories": ["pii.email"]}
            ],
            "egress": {"decision": "allow", "workspace_bundle_id": "pb_workspace_7"},
        },
    )
    async_db.add(
        RunCostEntry(
            run_id=run.id,
            step_id=step.id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            currency="USD",
            amount=Decimal("0.02"),
            billing_basis="tokens",
            billed_quantity=Decimal("40"),
        )
    )
    async_db.add(
        AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            event_type="gateway.request",
            resource_type="model",
            run_id=run.id,
            step_id=step.id,
            operation="invoke",
            outcome="allowed",
            payload_json={"tenant_bundle_id": "pb_tenant_3"},
        )
    )
    async_db.add(
        ApprovalRequest(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run.id,
            title="Issue a refund of 120 EUR",
            status="approved",
            details_json={"customer": "cust-42", "amount": 120},
            resolved_by="u-reviewer",
        )
    )
    async_db.add(
        Response(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run.id,
            model="model:test:chat",
            status="completed",
            input_json={},
            output_json={
                "text": "done",
                "citations": [{"chunk_id": "ch_1", "knowledge_id": "kb_1", "snippet": SNIPPET}],
            },
            usage_json={},
            metadata_json={},
        )
    )
    await async_db.commit()
    return run.id


def _open(content: bytes, run_id: str) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        prefix = f"evidence-{run_id}/"
        assert all(name.startswith(prefix) for name in bundle.namelist())
        return {name.removeprefix(prefix): bundle.read(name) for name in bundle.namelist()}


def _jsonl(body: bytes) -> list[dict]:
    return [json.loads(line) for line in body.decode().splitlines() if line.strip()]


async def test_the_bundle_holds_the_runs_evidence_and_checks_itself(async_client, async_db, ctx) -> None:
    run_id = await _governed_run(async_db, ctx)

    response = await async_client.get(f"/api/v1/runs/{run_id}/evidence")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert f'soit-evidence-{run_id}.zip' in response.headers["content-disposition"]
    assert response.headers["x-soit-evidence-sha256"] == hashlib.sha256(response.content).hexdigest()
    files = _open(response.content, run_id)

    # SHA256SUMS covers every other file, manifest included, as sha256sum -c reads it.
    sums = dict(reversed(line.split("  ", 1)) for line in files["SHA256SUMS"].decode().splitlines())
    assert set(sums) == set(files) - {"SHA256SUMS"}
    for path, digest in sums.items():
        assert hashlib.sha256(files[path]).hexdigest() == digest
    manifest = json.loads(files["manifest.json"])
    assert (manifest["schema"], manifest["version"], manifest["ledger_schema_version"]) == (
        "soit.evidence",
        "1.0",
        "1.0",
    )
    assert manifest["content_capture"] == "full"
    records = {item["path"]: item["records"] for item in manifest["files"]}
    assert records["steps.jsonl"] == 1 and records["costs.jsonl"] == 1 and records["audit.jsonl"] == 1

    ledger_documents = [json.loads(files["run.json"])]
    for path in ("steps.jsonl", "costs.jsonl", "audit.jsonl"):
        ledger_documents.extend(_jsonl(files[path]))
    for document in ledger_documents:
        assert validate_spec(document, LEDGER_SPEC) is True

    assert _jsonl(files["content_safety.jsonl"])[0]["categories"] == ["pii.email"]
    assert json.loads(files["policy.json"]) == {"policy_bundle_ids": ["pb_tenant_3", "pb_workspace_7"]}
    approval = _jsonl(files["approvals.jsonl"])[0]
    assert (approval["status"], approval["details"]["customer"]) == ("approved", "cust-42")
    assert _jsonl(files["citations.jsonl"])[0]["snippet"] == SNIPPET
    assert json.loads(files["governance.json"])


async def test_an_unchanged_run_gives_the_same_bundle_and_every_download_is_audited(
    async_client, async_db, ctx
) -> None:
    run_id = await _governed_run(async_db, ctx)

    first = await async_client.get(f"/api/v1/runs/{run_id}/evidence")
    second = await async_client.get(f"/api/v1/runs/{run_id}/evidence")

    assert first.content == second.content
    downloads = (
        await async_db.exec(select(AuditEvent).where(AuditEvent.event_type == "run.evidence_exported"))
    ).all()
    assert [(event.resource_id, event.run_id, event.payload_json["sha256"]) for event in downloads] == [
        (run_id, None, first.headers["x-soit-evidence-sha256"])
    ] * 2


async def test_a_metadata_only_workspace_gets_no_content_in_its_bundle(async_client, async_db, ctx) -> None:
    run_id = await _governed_run(async_db, ctx, capture="metadata_only")

    files = _open((await async_client.get(f"/api/v1/runs/{run_id}/evidence")).content, run_id)

    assert json.loads(files["manifest.json"])["content_capture"] == "metadata_only"
    approval = _jsonl(files["approvals.jsonl"])[0]
    assert approval["details"].startswith("[withheld:")
    assert approval["title"].startswith("[withheld:")
    citation = _jsonl(files["citations.jsonl"])[0]
    assert citation["snippet"].startswith("[withheld:")
    assert citation["chunk_id"] == "ch_1"
    for body in files.values():
        assert SNIPPET.encode() not in body
        assert b"cust-42" not in body


async def test_another_workspaces_run_is_not_found(async_client, async_db, ctx) -> None:
    run_id = await _governed_run(async_db, ctx)
    outsider = dataclasses.replace(ctx, workspace_id="another-workspace")
    app.dependency_overrides[get_current_context] = lambda: outsider
    try:
        response = await async_client.get(f"/api/v1/runs/{run_id}/evidence")
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert response.status_code == 404


async def test_a_bundle_that_cannot_tell_the_workspace_mode_withholds_content(async_db, ctx) -> None:
    from app.kernel.runtime.runs.content_capture import (
        get_workspace_capture_lookup,
        register_workspace_capture_lookup,
        reset_workspace_capture_lookup,
    )
    from app.modules.observe.application.evidence import RunEvidenceService

    run_id = await _governed_run(async_db, ctx)
    lookup = get_workspace_capture_lookup()
    reset_workspace_capture_lookup()
    try:
        bundle = await RunEvidenceService(async_db, ctx).build(run_id)
    finally:
        if lookup is not None:
            register_workspace_capture_lookup(lookup)

    assert bundle.manifest["content_capture"] == "metadata_only"
    assert SNIPPET.encode() not in bundle.content
