"""Entry-point contracts for governed image layer decomposition.

A decomposition is the same kind of spend as an edit, so it leaves the same
evidence: one run, one step, one cost row under its own operation name, billed
per returned image with the base included. What is new is the layer placement:
inline in the response, and as a ``layers.json`` run artifact when the images
go to run storage.
"""

import base64
import io
import json
from typing import Any

import pytest
from fastapi import status
from PIL import Image
from sqlmodel import select

from app.adapters.llm.memory import InMemoryLLMPort
from app.adapters.llm.volcengine_layers import ArkRequestError
from app.kernel.commons.errors import ForbiddenError
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.runs.exporter import to_runtrace_spec
from app.kernel.specs import validate_spec


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _decompose(async_client, **overrides):
    payload: dict[str, Any] = {
        "model": "model:test:seedream",
        "image_b64": base64.b64encode(_png()).decode("ascii"),
    }
    payload.update(overrides)
    return await async_client.post("/api/v1/images/decompositions", json=payload)


async def _run_records(async_db, run_id: str):
    run = await async_db.get(Run, run_id)
    steps = list((await async_db.exec(select(RunStep).where(RunStep.run_id == run_id))).all())
    costs = list((await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id))).all())
    artifacts = list((await async_db.exec(select(RunArtifact).where(RunArtifact.run_id == run_id))).all())
    return run, steps, costs, artifacts


class TestDecomposition:
    @pytest.mark.asyncio
    async def test_returns_the_base_and_placed_layers(self, async_client, async_db):
        response = await _decompose(async_client, max_layers=2, text_recognition=True, size="2K")

        assert response.status_code == status.HTTP_201_CREATED, response.json()
        body = response.json()["data"]
        assert body["status"] == "succeeded"
        assert body["base"]["b64_json"]
        assert [layer["z_index"] for layer in body["layers"]] == [1, 2]
        assert body["layers"][0]["bounding_box"] == [0, 0, 1, 1]
        assert body["layers"][0]["image"]["b64_json"]
        assert body["base_size"] == "1x1"
        assert body["layers"][0]["text"] == "hello"
        assert body["layers"][0]["text_lines"][0]["text"] == "hello"
        assert body["layers"][1]["text"] is None
        assert body["manifest_artifact_id"] is None

    @pytest.mark.asyncio
    async def test_bills_every_returned_image_under_its_own_operation(self, async_client, async_db):
        body = (await _decompose(async_client, max_layers=2, size="2K")).json()["data"]

        run, steps, costs, _ = await _run_records(async_db, body["run_id"])
        assert run.mode == "image"
        assert run.status == "succeeded"
        assert len(steps) == 1
        assert steps[0].metrics_json["image_count"] == 3
        assert steps[0].metrics_json["layer_count"] == 2
        assert len(costs) == 1
        assert costs[0].billing_basis == "images"
        assert costs[0].billed_quantity == 3
        assert costs[0].operation == "decompose_image"
        assert costs[0].pricing_snapshot_json["quantities"]["size"] == "2K"

        document = to_runtrace_spec(run, steps, cost_entries=costs)
        assert validate_spec(document, "runtrace_spec") is True

    @pytest.mark.asyncio
    async def test_artifact_job_keeps_a_layer_manifest(self, async_client, async_db):
        body = (await _decompose(async_client, max_layers=2, response_format="artifact")).json()["data"]

        assert body["base"]["artifact_id"]
        assert all(layer["image"]["artifact_id"] for layer in body["layers"])
        manifest_id = body["manifest_artifact_id"]
        assert manifest_id

        _, _, _, artifacts = await _run_records(async_db, body["run_id"])
        assert len(artifacts) == 4
        manifest = next(artifact for artifact in artifacts if artifact.id == manifest_id)
        assert manifest.meta_json["kind"] == "image_layers"

        download = await async_client.get(
            f"/api/v1/runs/{body['run_id']}/artifacts/{manifest_id}/content"
        )
        assert download.status_code == status.HTTP_200_OK
        content = json.loads(download.content)
        assert content["base"]["artifact_id"] == body["base"]["artifact_id"]
        assert [layer["artifact_id"] for layer in content["layers"]] == [
            layer["image"]["artifact_id"] for layer in body["layers"]
        ]
        assert content["layers"][0]["bounding_box"] == [0, 0, 1, 1]
        assert content["base"]["size"] == "1x1"

    @pytest.mark.asyncio
    async def test_url_job_returns_provider_links_with_the_placement(self, async_client, async_db):
        body = (await _decompose(async_client, max_layers=2, text_recognition=True, response_format="url")).json()[
            "data"
        ]

        assert body["base"]["url"] == "https://images.test/seedream/base.png"
        assert body["base"]["b64_json"] is None
        assert [layer["image"]["url"] for layer in body["layers"]] == [
            "https://images.test/seedream/layer-1.png",
            "https://images.test/seedream/layer-2.png",
        ]
        assert body["layers"][0]["bounding_box"] == [0, 0, 1, 1]
        assert body["layers"][0]["text"] == "hello"
        assert body["base_size"] == "1x1"
        assert body["manifest_artifact_id"] is None

        _, _, costs, artifacts = await _run_records(async_db, body["run_id"])
        assert costs[0].billed_quantity == 3
        assert all(artifact.meta_json.get("kind") != "image_layers" for artifact in artifacts)

    @pytest.mark.asyncio
    async def test_needs_exactly_one_source(self, async_client):
        response = await async_client.post(
            "/api/v1/images/decompositions", json={"model": "model:test:seedream"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_refuses_a_size_that_is_not_a_tier(self, async_client):
        response = await _decompose(async_client, size="1024x1024")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestProviderFailure:
    """What the caller is told when the provider, not SOIT, failed the call."""

    @pytest.mark.asyncio
    async def test_a_provider_failure_is_not_an_internal_error(self, async_client, async_db, monkeypatch):
        async def failing(*_args, **_kwargs):
            raise ArkRequestError(None, "ConnectError", "the provider could not be reached")

        monkeypatch.setattr(InMemoryLLMPort, "decompose_image", failing)

        response = await _decompose(async_client, max_layers=2)

        assert response.status_code == status.HTTP_502_BAD_GATEWAY, response.json()
        assert response.json()["code"] == "MODEL_PROVIDER_FAILED"
        run = (await async_db.exec(select(Run).where(Run.mode == "image"))).all()[-1]
        assert run.status == "failed"
        assert run.error_code == "MODEL_PROVIDER_FAILED"

    @pytest.mark.asyncio
    async def test_a_provider_moderation_refusal_reaches_the_caller(self, async_client, monkeypatch):
        async def refusing(*_args, **_kwargs):
            raise ForbiddenError(
                "The provider refused the image under its content policy",
                {
                    "provider": "volcengine",
                    "direction": "inbound",
                    "provider_error_code": "InputImageSensitiveContentDetected",
                    "categories": ["provider_content_policy"],
                },
            )

        monkeypatch.setattr(InMemoryLLMPort, "decompose_image", refusing)

        response = await _decompose(async_client, max_layers=2)

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.json()
        body = response.json()
        assert body["code"] == "FORBIDDEN"
        assert body["details"]["categories"] == ["provider_content_policy"]
        assert body["details"]["direction"] == "inbound"
