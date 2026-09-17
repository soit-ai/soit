"""Entry-point contracts for governed image editing (M1).

The edit endpoint reuses the generation governance chain, so these assert the
same evidence appears — one run, one step, one cost row — under its own
operation name, plus the parts unique to editing: the mask convention, the
input resolution rules, and the parameters that must not be dropped in silence.
"""

import base64
import io
from typing import Any

import pytest
from fastapi import status
from PIL import Image
from sqlmodel import select

from app.kernel.ports.llm.interface import ImageGenerationResponse
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.specs import validate_spec
from app.wiring import get_container


def _png(size=(64, 64), colour=(10, 20, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _mask_png(size=(64, 64)) -> bytes:
    """Left half white, meaning "edit here" under SOIT's convention."""
    mask = Image.new("L", size, 0)
    for x in range(size[0] // 2):
        for y in range(size[1]):
            mask.putpixel((x, y), 255)
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


async def _edit(async_client, **overrides):
    payload: dict[str, Any] = {
        "model": "model:test:seedream",
        "prompt": "a red dot",
        "image_b64": _b64(_png()),
    }
    payload.update(overrides)
    return await async_client.post("/api/v1/images/edits", json=payload)


async def _run_records(async_db, run_id: str) -> tuple[Run, list[RunStep], list[RunCostEntry]]:
    run = await async_db.get(Run, run_id)
    steps = list((await async_db.exec(select(RunStep).where(RunStep.run_id == run_id))).all())
    costs = list((await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id))).all())
    return run, steps, costs


class _FailingLLMPort:
    def __init__(self) -> None:
        self.calls = 0

    async def edit_image(self, **kwargs: Any) -> ImageGenerationResponse:
        del kwargs
        self.calls += 1
        raise RuntimeError("Provider is unavailable")


class TestGovernanceEvidence:
    @pytest.mark.asyncio
    async def test_edit_records_run_step_and_image_usage(self, async_client, async_db, ctx):
        response = await _edit(async_client, n=2, size="1024x1024", mask_b64=_b64(_mask_png()))

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()["data"]
        assert len(body["data"]) == 2
        assert all(image["b64_json"] for image in body["data"])

        run, steps, costs = await _run_records(async_db, body["run_id"])
        assert (run.tenant_id, run.workspace_id) == (ctx.tenant_id, ctx.workspace_id)
        assert run.mode == "image"
        assert run.status == "succeeded"

        assert len(steps) == 1
        assert steps[0].step_type == "llm"
        assert steps[0].status == "succeeded"
        assert steps[0].metrics_json["image_count"] == 2

        assert len(costs) == 1
        usage = costs[0]
        assert usage.step_id == steps[0].id
        assert usage.billing_basis == "images"
        assert usage.billed_quantity == 2
        assert usage.source_port == "llm"
        # The ledger must tell an edit apart from a generation.
        assert usage.operation == "edit_image"

    @pytest.mark.asyncio
    async def test_cost_snapshot_records_the_request_shape(self, async_client, async_db):
        # M4(2): four 4096px images and four 256px images bill identically per
        # image, so the snapshot has to carry what was actually asked for.
        response = await _edit(async_client, size="1024x1024")
        _, _, costs = await _run_records(async_db, response.json()["data"]["run_id"])

        quantities = costs[0].pricing_snapshot_json["quantities"]
        assert quantities["images"] == 1
        assert quantities["size"] == "1024x1024"

    @pytest.mark.asyncio
    async def test_edit_run_export_matches_runtrace_contract(self, async_client, async_db):
        response = await _edit(async_client)
        run, steps, costs = await _run_records(async_db, response.json()["data"]["run_id"])

        document = to_runtrace_spec(run, steps, cost_entries=costs)
        assert document["run"]["kind"] == "image"
        assert validate_spec(document, "runtrace_spec") is True

    @pytest.mark.asyncio
    async def test_failure_fails_the_run_without_re_billing(self, async_client, async_db):
        container = get_container()
        original = container.get("llm_port")
        failing = _FailingLLMPort()
        container.register_singleton("llm_port", failing)
        try:
            response = await _edit(async_client)
        finally:
            container.register_singleton("llm_port", original)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        # An image call the provider may already have billed is never retried.
        assert failing.calls == 1

        run = (await async_db.exec(select(Run).where(Run.mode == "image"))).one()
        assert run.status == "failed"
        assert run.error_code == "IMAGE_ERROR"
        assert (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run.id))).all() == []


class TestMaskContract:
    @pytest.mark.asyncio
    async def test_response_states_the_mask_convention(self, async_client):
        # The convention is published with the result so a caller never has to
        # guess which way round their mask should be drawn.
        response = await _edit(async_client, mask_b64=_b64(_mask_png()))
        assert response.json()["data"]["mask_convention"] == "white_is_edit_region"

    @pytest.mark.asyncio
    async def test_mask_reaches_the_adapter(self, async_client):
        container = get_container()
        port = container.get("llm_port")
        port.last_edit = None

        await _edit(async_client, mask_b64=_b64(_mask_png()))

        assert port.last_edit is not None
        assert port.last_edit["mask_bytes"] > 0

    @pytest.mark.asyncio
    async def test_edit_without_a_mask_is_accepted(self, async_client):
        # Reference editing: the whole image is the subject, no selection.
        container = get_container()
        port = container.get("llm_port")
        port.last_edit = None

        response = await _edit(async_client)

        assert response.status_code == status.HTTP_201_CREATED
        assert port.last_edit["mask_bytes"] == 0

    @pytest.mark.asyncio
    async def test_mask_of_a_different_size_is_refused(self, async_client, async_db):
        response = await _edit(async_client, mask_b64=_b64(_mask_png((32, 32))))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must match" in response.json()["message"]
        # Refused before any run was opened, so nothing was billed.
        assert (await async_db.exec(select(Run).where(Run.mode == "image"))).all() == []


class TestInputResolution:
    @pytest.mark.asyncio
    async def test_image_is_required(self, async_client):
        response = await async_client.post(
            "/api/v1/images/edits",
            json={"model": "model:test:m", "prompt": "hi"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_two_image_sources_are_refused(self, async_client):
        # Ambiguous input is refused rather than one source silently winning.
        response = await _edit(async_client, image_attachment_id="att_1")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_two_mask_sources_are_refused(self, async_client):
        response = await _edit(
            async_client, mask_b64=_b64(_mask_png()), mask_attachment_id="att_1"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_malformed_base64_is_refused(self, async_client):
        response = await _edit(async_client, image_b64="!!!not base64!!!")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_image_can_come_from_an_attachment(self, async_client):
        upload = await async_client.post(
            "/api/v1/attachments",
            files={"file": ("source.png", _png(), "image/png")},
        )
        assert upload.status_code == status.HTTP_201_CREATED
        attachment_id = upload.json()["data"]["id"]

        response = await async_client.post(
            "/api/v1/images/edits",
            json={
                "model": "model:test:m",
                "prompt": "a red dot",
                "image_attachment_id": attachment_id,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["data"]["data"][0]["b64_json"]

    @pytest.mark.asyncio
    async def test_mask_can_come_from_an_attachment(self, async_client):
        source = (await async_client.post(
            "/api/v1/attachments",
            files={"file": ("source.png", _png(), "image/png")},
        )).json()["data"]["id"]
        mask = (await async_client.post(
            "/api/v1/attachments",
            files={"file": ("mask.png", _mask_png(), "image/png")},
        )).json()["data"]["id"]

        response = await async_client.post(
            "/api/v1/images/edits",
            json={
                "model": "model:test:m",
                "prompt": "a red dot",
                "image_attachment_id": source,
                "mask_attachment_id": mask,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.asyncio
    async def test_non_image_attachment_is_refused(self, async_client):
        attachment_id = (await async_client.post(
            "/api/v1/attachments",
            files={"file": ("notes.txt", b"plain text", "text/plain")},
        )).json()["data"]["id"]

        response = await async_client.post(
            "/api/v1/images/edits",
            json={
                "model": "model:test:m",
                "prompt": "a red dot",
                "image_attachment_id": attachment_id,
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not an image" in response.json()["message"]


class TestPassThroughParameters:
    @pytest.mark.asyncio
    async def test_reproducibility_parameters_reach_the_adapter(self, async_client):
        # Dropping a seed in silence would make a request the caller believes
        # is reproducible quietly not be.
        container = get_container()
        port = container.get("llm_port")
        port.last_edit = None

        await _edit(
            async_client,
            seed=1234,
            strength=0.65,
            negative_prompt="blurry",
            background="transparent",
            output_format="webp",
        )

        passed = port.last_edit["kwargs"]
        assert passed["seed"] == 1234
        assert passed["strength"] == 0.65
        assert passed["negative_prompt"] == "blurry"
        assert passed["background"] == "transparent"
        assert passed["output_format"] == "webp"

    @pytest.mark.asyncio
    async def test_unset_parameters_are_not_invented(self, async_client):
        container = get_container()
        port = container.get("llm_port")
        port.last_edit = None

        await _edit(async_client)

        passed = port.last_edit["kwargs"]
        for name in ("seed", "strength", "negative_prompt", "background"):
            assert name not in passed

    @pytest.mark.asyncio
    async def test_out_of_range_values_are_refused(self, async_client):
        for overrides in ({"strength": 1.5}, {"n": 99}, {"size": "16x16"}):
            response = await _edit(async_client, **overrides)
            assert response.status_code == status.HTTP_400_BAD_REQUEST, overrides
            assert response.json()["code"] == "VALIDATION_ERROR"
