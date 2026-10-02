"""A run keeps what retrieval returned; reading it back obeys who may read that now.

A citation, a knowledge query result and a source event stored while a
document was readable are left out for a member it is restricted from, and
still shown to an admin.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run, RunStep, RunStepToolCall
from app.kernel.runtime.runs.knowledge_redaction import (
    register_knowledge_read_filter,
    reset_knowledge_read_filter,
)
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.knowledge.domain.models import Knowledge, KnowledgeDocumentRestriction
from app.modules.knowledge.infra.read_filter import KnowledgeDocumentReadFilter

pytestmark = pytest.mark.asyncio


class _NoGrants:
    async def allows_resource_action(self, **kwargs) -> bool:
        del kwargs
        return False


@pytest.fixture(autouse=True)
def _knowledge_filter(monkeypatch):
    # Registered as the app registers it; tests start with kernel lookups cleared.
    register_knowledge_read_filter(KnowledgeDocumentReadFilter())
    # The app's own grant lookup opens a session of its own; no member holds a grant here.
    monkeypatch.setattr("app.modules.knowledge.application.document_access.get_resource_grant_provider", _NoGrants)
    monkeypatch.setattr("app.modules.knowledge.infra.read_filter.get_resource_grant_provider", _NoGrants)
    yield
    reset_knowledge_read_filter()


def _citation(doc_key: str) -> dict:
    return {
        "chunk_id": f"ck_{doc_key}",
        "document_id": f"doc_{doc_key}",
        "knowledge_id": "kb_hr",
        "doc_key": doc_key,
        "snippet": f"secret text of {doc_key}",
    }


async def _seed(async_db, ctx: RequestContext) -> None:
    scope = {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id}
    async_db.add(Knowledge(id="kb_hr", name="HR", type="document", visibility="workspace", created_by="u_owner", **scope))
    async_db.add(KnowledgeDocumentRestriction(knowledge_id="kb_hr", doc_key="payroll", created_by="u_owner", **scope))
    async_db.add(Run(id="run_rag", user_id="u_owner", mode="agent", kind="agent", status="succeeded", started_at=utc_now(), **scope))
    async_db.add(RunStep(id="step_tool", run_id="run_rag", step_type="tool", status="succeeded", **scope))
    async_db.add(
        RunStepToolCall(
            run_id="run_rag",
            run_step_id="step_tool",
            tool_call_id="call_1",
            idempotency_key="idem_1",
            request_hash="hash_1",
            tool_ref="tool:function:knowledge_query",
            status="succeeded",
            result_json={
                "result": {
                    "results": [
                        {"chunk_id": "ck_travel", "document_id": "doc_travel", "text": "trips", "metadata": {"knowledge_id": "kb_hr", "doc_key": "travel"}},
                        {"chunk_id": "ck_payroll", "document_id": "doc_payroll", "text": "salaries", "metadata": {"knowledge_id": "kb_hr", "doc_key": "payroll"}},
                    ],
                    "total": 2,
                    "citations": [_citation("travel"), _citation("payroll")],
                }
            },
            **scope,
        )
    )
    async_db.add(
        Response(
            id="resp_rag",
            run_id="run_rag",
            status="succeeded",
            output_json={"text": "answer", "citations": [_citation("travel"), _citation("payroll")]},
            **scope,
        )
    )
    async_db.add(
        ResponseEvent(
            response_id="resp_rag",
            run_id="run_rag",
            sequence=1,
            type="CUSTOM",
            payload_json={"type": "CUSTOM", "name": "soit.source", "value": {"schemaVersion": 1, **_citation("payroll")}},
            **scope,
        )
    )
    await async_db.commit()


def _as(ctx: RequestContext, user_id: str, role: str) -> None:
    member = replace(ctx, user_id=user_id, workspace_role=role, tenant_role="Member")
    app.dependency_overrides[get_current_context] = lambda: member


async def _read(async_client) -> dict:
    run = (await async_client.get("/api/v1/runs/run_rag")).json()["data"]
    response = (await async_client.get("/api/v1/responses/resp_rag")).json()["data"]
    events = (await async_client.get("/api/v1/responses/resp_rag/events")).json()["data"]
    return {"run": run, "response": response, "events": events}


async def test_a_member_reads_the_run_without_the_restricted_document(async_client, async_db, ctx) -> None:
    await _seed(async_db, ctx)
    _as(ctx, "u_dev", "Dev")
    try:
        seen = await _read(async_client)
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    run = seen["run"]
    assert [c["doc_key"] for c in run["citations"]] == ["travel"]
    [tool_call] = run["tool_calls"]
    result = tool_call["result_json"]["result"]
    assert [r["metadata"]["doc_key"] for r in result["results"]] == ["travel"]
    assert result["total"] == 1
    assert [c["doc_key"] for c in seen["response"]["output_json"]["citations"]] == ["travel"]
    events = seen["events"]["items"] if isinstance(seen["events"], dict) else seen["events"]
    assert set(events[0]["payload_json"]["value"]) == {"withheld"}
    assert "secret text of payroll" not in str(seen)


async def test_an_admin_still_reads_everything(async_client, async_db, ctx) -> None:
    await _seed(async_db, ctx)
    _as(ctx, "u_admin", "Admin")
    try:
        seen = await _read(async_client)
    finally:
        app.dependency_overrides[get_current_context] = lambda: ctx

    assert [c["doc_key"] for c in seen["run"]["citations"]] == ["travel", "payroll"]
    assert seen["run"]["tool_calls"][0]["result_json"]["result"]["total"] == 2
    events = seen["events"]["items"] if isinstance(seen["events"], dict) else seen["events"]
    assert events[0]["payload_json"]["value"]["doc_key"] == "payroll"
