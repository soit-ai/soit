"""Entry-point contracts for governed text embeddings."""

from typing import Any

from fastapi import status
from sqlmodel import select

from app.kernel.ports.llm.interface import EmbeddingResponse
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.specs import validate_spec
from app.wiring import get_container


class _FailingLLMPort:
    """Embedding port that always fails."""

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, **kwargs: Any) -> EmbeddingResponse:
        del kwargs
        self.calls += 1
        raise RuntimeError("Provider is unavailable")


def _embed(client, **overrides):
    payload: dict[str, Any] = {"model": "model:test:embedder", "input": ["alpha", "beta"]}
    payload.update(overrides)
    return client.post("/api/v1/embeddings", json=payload)


def _run_records(db, run_id: str) -> tuple[Run, list[RunStep], list[RunCostEntry]]:
    run = db.get(Run, run_id)
    steps = list(db.exec(select(RunStep).where(RunStep.run_id == run_id)).all())
    costs = list(db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id)).all())
    return run, steps, costs


def test_embeddings_records_run_step_and_usage(client, db, ctx):
    response = _embed(client)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()["data"]
    assert len(body["embeddings"]) == 2
    assert all(isinstance(vector, list) and vector for vector in body["embeddings"])

    run, steps, costs = _run_records(db, body["run_id"])
    assert run is not None
    assert (run.tenant_id, run.workspace_id) == (ctx.tenant_id, ctx.workspace_id)
    assert run.mode == "embedding"
    assert run.kind == "embedding"
    assert run.status == "succeeded"

    assert len(steps) == 1
    assert steps[0].step_type == "retrieval"
    assert steps[0].status == "succeeded"
    assert steps[0].metrics_json is not None
    assert steps[0].metrics_json["embedding_count"] == 2

    assert len(costs) == 1
    usage = costs[0]
    assert usage.step_id == steps[0].id
    assert usage.billing_basis == "embeddings"
    assert usage.billed_quantity == 2
    assert usage.source_port == "llm"
    assert usage.operation == "embed"
    # Embeddings bill by input tokens: the ledger column says "embeddings",
    # the pricing snapshot carries the token basis it was priced under.
    assert usage.pricing_snapshot_json["billing_basis"] == "tokens"
    # The in-memory route carries no pricing, so the row stays auditable but unpriced.
    assert usage.pricing_snapshot_json["priced"] is False


def test_embeddings_accepts_single_string_input(client):
    response = _embed(client, input="just one text")

    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.json()["data"]["embeddings"]) == 1


def test_embeddings_run_export_matches_runtrace_contract(client, db):
    response = _embed(client)

    assert response.status_code == status.HTTP_201_CREATED
    run, steps, costs = _run_records(db, response.json()["data"]["run_id"])

    document = to_runtrace_spec(run, steps, cost_entries=costs)

    assert document["run"]["kind"] == "embedding"
    assert validate_spec(document, "runtrace_spec") is True


def test_embeddings_rejects_oversized_and_blank_input(client):
    # The platform envelope maps request-validation failures to 400.
    assert _embed(client, input=[]).status_code == status.HTTP_400_BAD_REQUEST
    assert _embed(client, input=["  "]).status_code == status.HTTP_400_BAD_REQUEST
    assert _embed(client, input=["x"] * 257).status_code == status.HTTP_400_BAD_REQUEST


def test_embeddings_failure_fails_the_run(client, db):
    container = get_container()
    original_port = container.get("llm_port")
    failing_port = _FailingLLMPort()
    container.register_singleton("llm_port", failing_port)
    try:
        response = _embed(client)
    finally:
        container.register_singleton("llm_port", original_port)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # Unlike image generation, embeddings are idempotent: the gateway's retry
    # policy is allowed to re-attempt before the run is failed.
    assert failing_port.calls >= 1
