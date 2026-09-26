"""The ``soit`` CLI works against the real API, not only against stand-ins.

The CLI is synchronous and the app under test is served in-process, so each
CLI request is bridged onto the test's event loop. What is exercised is the
real server: its envelope, headers, file names and digests.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.runs import RunCostEntry
from app.kernel.runtime.runs.writer import TraceWriter
from app.main import app
from app.modules.agent.application.application_service import AgentApplicationService

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "cli"))

from soit_cli.main import EXIT_OK, main  # noqa: E402

pytestmark = pytest.mark.asyncio


class _Bridge(httpx.BaseTransport):
    """Send the CLI's requests through the test's ASGI client, on its loop."""

    def __init__(self, client: httpx.AsyncClient, loop: asyncio.AbstractEventLoop) -> None:
        self.client = client
        self.loop = loop

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        forwarded = self.client.build_request(
            request.method, str(request.url), headers=request.headers, content=request.read()
        )
        response = asyncio.run_coroutine_threadsafe(self.client.send(forwarded), self.loop).result(timeout=120)
        return httpx.Response(response.status_code, headers=response.headers, content=response.content)


@pytest.fixture(autouse=True)
def _signed_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.wiring import get_container

    get_container()
    monkeypatch.setenv("SOIT_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setenv("SOIT_API_URL", "http://testserver")
    monkeypatch.setenv("SOIT_API_KEY", "sk-compat-not-a-real-key")


async def _soit(async_client: httpx.AsyncClient, *argv: str) -> int:
    bridge = _Bridge(async_client, asyncio.get_running_loop())
    return await asyncio.to_thread(main, list(argv), transport=bridge)


async def _run_with_cost(async_db, ctx) -> str:
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent", subject_kind="agent", subject_id="agt_cli")
    step = await writer.create_step(run_id=run.id, step_type="llm", step_id="answer")
    async_db.add(
        RunCostEntry(
            run_id=run.id,
            step_id=step.id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            currency="USD",
            amount=Decimal("0.03"),
            billing_basis="tokens",
            billed_quantity=Decimal("30"),
        )
    )
    await async_db.commit()
    return run.id


async def test_evidence_is_exported_and_checked_end_to_end(async_client, async_db, ctx, tmp_path, capsys) -> None:
    run_id = await _run_with_cost(async_db, ctx)
    target = tmp_path / "bundle.zip"

    code = await _soit(async_client, "export", "evidence", run_id, "-o", str(target))

    assert code == EXIT_OK, capsys.readouterr().err
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    assert digest in capsys.readouterr().err
    with zipfile.ZipFile(target) as bundle:
        assert f"evidence-{run_id}/SHA256SUMS" in bundle.namelist()


async def test_ledger_records_are_exported_end_to_end(async_client, async_db, ctx, tmp_path, capsys) -> None:
    await _run_with_cost(async_db, ctx)
    target = tmp_path / "costs.csv"

    since = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    code = await _soit(async_client, "export", "costs", "--since", since, "--format", "csv", "-o", str(target))

    assert code == EXIT_OK, capsys.readouterr().err
    header, row = target.read_text(encoding="utf-8").splitlines()[:2]
    assert header.startswith("cost_entry_id,")
    assert "0.03" in row


async def test_an_agent_runs_end_to_end(async_client, async_db, ctx, capsys) -> None:
    class _Answer(LLMPort):
        async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
            return ChatResponse(text="Refunds take 14 days.", tokens_prompt=4, tokens_completion=6, finish_reason="stop")

        async def embed(self, texts, model, **kwargs):
            raise NotImplementedError

        async def rerank(self, query, documents, model, top_n=None, **kwargs):
            raise NotImplementedError

    class _Tools(ToolPort):
        async def invoke(self, tool_ref, parameters, **kwargs):
            return ToolResponse(result={})

    async def build() -> AgentApplicationService:
        return AgentApplicationService(db=async_db, ctx=ctx, llm_port=_Answer(), tool_port=_Tools())

    app.dependency_overrides[get_agent_application_service] = build
    try:
        agent_id = (await async_client.post("/api/v1/agents", json={"name": "cli-agent"})).json()["data"]["id"]
        version = await async_client.post(
            f"/api/v1/agents/{agent_id}/versions", json={"bindings": {"model_ref": "model:test:chat"}}
        )
        await async_client.post(
            f"/api/v1/agents/{agent_id}/publish", json={"version_id": version.json()["data"]["id"]}
        )

        code = await _soit(async_client, "run", agent_id, "How long do refunds take?")
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)

    out = capsys.readouterr()
    assert code == EXIT_OK, out.err
    # The app under test logs to standard output too; the answer is its own line.
    assert "Refunds take 14 days." in out.out.splitlines()
    assert "10 tokens" in out.err
