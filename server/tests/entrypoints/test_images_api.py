"""Entry-point contracts for governed image generation."""

from typing import Any

from fastapi import status
from sqlmodel import select

from app.kernel.ports.llm.interface import ImageGenerationResponse
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.specs import validate_spec
from app.wiring import get_container


class _FailingLLMPort:
    """Image port that fails with an error the retry policy treats as retryable."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_image(self, **kwargs: Any) -> ImageGenerationResponse:
        del kwargs
        self.calls += 1
        raise RuntimeError("Provider is unavailable")


def _generate(client, **overrides):
    payload: dict[str, Any] = {"model": "model:test:seedream", "prompt": "a red dot"}
    payload.update(overrides)
    return client.post("/api/v1/images/generations", json=payload)


def _run_records(db, run_id: str) -> tuple[Run, list[RunStep], list[RunCostEntry]]:
    run = db.get(Run, run_id)
    steps = list(db.exec(select(RunStep).where(RunStep.run_id == run_id)).all())
    costs = list(db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id)).all())
    return run, steps, costs


def test_image_generation_records_run_step_and_image_usage(client, db, ctx):
    response = _generate(client, n=2, size="1024x1024")

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()["data"]
    assert len(body["data"]) == 2
    assert all(image["b64_json"] for image in body["data"])

    run, steps, costs = _run_records(db, body["run_id"])
    assert run is not None
    assert (run.tenant_id, run.workspace_id) == (ctx.tenant_id, ctx.workspace_id)
    assert run.mode == "image"
    assert run.kind == "image"
    assert run.status == "succeeded"

    assert len(steps) == 1
    assert steps[0].step_type == "llm"
    assert steps[0].status == "succeeded"
    assert steps[0].metrics_json is not None
    assert steps[0].metrics_json["image_count"] == 2

    assert len(costs) == 1
    usage = costs[0]
    assert usage.step_id == steps[0].id
    assert usage.billing_basis == "images"
    assert usage.billed_quantity == 2
    assert usage.request_count == 2
    assert usage.source_port == "llm"
    assert usage.operation == "generate_image"
    assert usage.pricing_snapshot_json["billing_basis"] == "images"
    assert usage.pricing_snapshot_json["quantities"]["images"] == 2
    # The in-memory route carries no pricing, so the row stays auditable but unpriced.
    assert usage.pricing_snapshot_json["priced"] is False


def test_image_run_export_matches_runtrace_contract(client, db):
    response = _generate(client)

    assert response.status_code == status.HTTP_201_CREATED
    run, steps, costs = _run_records(db, response.json()["data"]["run_id"])

    document = to_runtrace_spec(run, steps, cost_entries=costs)

    assert document["run"]["kind"] == "image"
    assert validate_spec(document, "runtrace_spec") is True


def test_image_generation_failure_fails_the_run_without_re_billing(client, db):
    container = get_container()
    original_port = container.get("llm_port")
    failing_port = _FailingLLMPort()
    container.register_singleton("llm_port", failing_port)
    try:
        response = _generate(client)
    finally:
        container.register_singleton("llm_port", original_port)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # A failed image call must not be retried: the provider may already have
    # generated and billed the images the platform never received.
    assert failing_port.calls == 1

    run = db.exec(select(Run).where(Run.mode == "image")).one()
    assert run.status == "failed"
    assert run.error_code == "IMAGE_ERROR"
    assert db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run.id)).all() == []


def test_image_generation_rejects_unsupported_dimensions(client, db):
    for size in ("16x16", "9999x9999"):
        response = _generate(client, size=size)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "VALIDATION_ERROR"
    assert db.exec(select(Run).where(Run.mode == "image")).all() == []
