"""Entry-point contracts for governed image generation."""

from typing import Any

import pytest
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


async def _generate(async_client, **overrides):
    payload: dict[str, Any] = {"model": "model:test:seedream", "prompt": "a red dot"}
    payload.update(overrides)
    return await async_client.post("/api/v1/images/generations", json=payload)


async def _run_records(async_db, run_id: str) -> tuple[Run, list[RunStep], list[RunCostEntry]]:
    run = await async_db.get(Run, run_id)
    steps = list((await async_db.exec(select(RunStep).where(RunStep.run_id == run_id))).all())
    costs = list((await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id))).all())
    return run, steps, costs


@pytest.mark.asyncio
async def test_image_generation_records_run_step_and_image_usage(async_client, async_db, ctx):
    response = await _generate(async_client, n=2, size="1024x1024")

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()["data"]
    assert len(body["data"]) == 2
    assert all(image["b64_json"] for image in body["data"])

    run, steps, costs = await _run_records(async_db, body["run_id"])
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


@pytest.mark.asyncio
async def test_image_run_export_matches_runtrace_contract(async_client, async_db):
    response = await _generate(async_client)

    assert response.status_code == status.HTTP_201_CREATED
    run, steps, costs = await _run_records(async_db, response.json()["data"]["run_id"])

    document = to_runtrace_spec(run, steps, cost_entries=costs)

    assert document["run"]["kind"] == "image"
    assert validate_spec(document, "runtrace_spec") is True


@pytest.mark.asyncio
async def test_image_generation_failure_fails_the_run_without_re_billing(async_client, async_db):
    container = get_container()
    original_port = container.get("llm_port")
    failing_port = _FailingLLMPort()
    container.register_singleton("llm_port", failing_port)
    try:
        response = await _generate(async_client)
    finally:
        container.register_singleton("llm_port", original_port)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # A failed image call must not be retried: the provider may already have
    # generated and billed the images the platform never received.
    assert failing_port.calls == 1

    run = (await async_db.exec(select(Run).where(Run.mode == "image"))).one()
    assert run.status == "failed"
    assert run.error_code == "IMAGE_ERROR"
    assert (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run.id))).all() == []


@pytest.mark.asyncio
async def test_image_generation_rejects_unsupported_dimensions(async_client, async_db):
    for size in ("16x16", "9999x9999"):
        response = await _generate(async_client, size=size)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "VALIDATION_ERROR"
    assert (await async_db.exec(select(Run).where(Run.mode == "image"))).all() == []


class TestGenerationOptions:
    """background and output_format reach generation as they already reached edits."""

    @pytest.mark.asyncio
    async def test_they_reach_the_adapter(self, async_client):
        port = get_container().get("llm_port")
        port.last_generate = None

        response = await _generate(async_client, background="transparent", output_format="webp")

        assert response.status_code == status.HTTP_201_CREATED, response.text
        passed = port.last_generate["kwargs"]
        assert passed["background"] == "transparent"
        assert passed["output_format"] == "webp"

    @pytest.mark.asyncio
    async def test_unset_options_are_not_invented(self, async_client):
        port = get_container().get("llm_port")
        port.last_generate = None

        await _generate(async_client)

        passed = port.last_generate["kwargs"]
        assert "background" not in passed
        assert "output_format" not in passed

    @pytest.mark.asyncio
    @pytest.mark.parametrize("overrides", [{"background": "checkered"}, {"output_format": "gif"}])
    async def test_unknown_values_are_refused_before_a_run_opens(
        self, async_client, async_db, overrides
    ):
        response = await _generate(async_client, **overrides)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert (await async_db.exec(select(Run).where(Run.mode == "image"))).all() == []


class TestFieldsGenerationDoesNotTake:
    """A field the request does not model is refused, not dropped while the image bills."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "field, value",
        [
            ("seed", 7),
            ("strength", 0.5),
            ("negative_prompt", "blurry"),
            ("quality", "high"),
            ("steps", 30),
            ("style", "vivid"),
        ],
    )
    async def test_it_is_refused_before_a_run_opens(self, async_client, async_db, field, value):
        port = get_container().get("llm_port")
        port.last_generate = None

        response = await _generate(async_client, **{field: value})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert [error["field"] for error in body["details"]["errors"]] == [f"body.{field}"]
        assert port.last_generate is None
        assert (await async_db.exec(select(Run).where(Run.mode == "image"))).all() == []
        assert (await async_db.exec(select(RunCostEntry))).all() == []

    @pytest.mark.asyncio
    async def test_every_such_field_is_named(self, async_client):
        response = await _generate(async_client, seed=7, quality="high")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        fields = {error["field"] for error in response.json()["details"]["errors"]}
        assert fields == {"body.seed", "body.quality"}

    @pytest.mark.asyncio
    async def test_the_async_flag_is_still_taken_by_its_name(self, async_client):
        response = await _generate(async_client, **{"async": True})

        assert response.status_code == status.HTTP_202_ACCEPTED, response.text
