"""Asynchronous image jobs and artifact returns (M2).

The inline shape has a ceiling: four 2048px images are 10-16 MB of base64 in one
response body, and providers routinely spend minutes on a batch. These cover the
two ways out of that — results into governed run storage, and a run id returned
before the work finishes — plus the property that matters most, that neither
changes what the synchronous caller already gets.
"""

import asyncio
import base64
import io
from typing import Any

import pytest
from fastapi import status
from PIL import Image
from sqlmodel import select

from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry
from app.kernel.runtime.images.service import ImageJobRequest


def _png(size=(64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _generate(async_client, **overrides):
    payload: dict[str, Any] = {"model": "model:test:seedream", "prompt": "a red dot"}
    payload.update(overrides)
    return await async_client.post("/api/v1/images/generations", json=payload)


async def _edit(async_client, **overrides):
    payload: dict[str, Any] = {
        "model": "model:test:seedream",
        "prompt": "a red dot",
        "image_b64": base64.b64encode(_png()).decode("ascii"),
    }
    payload.update(overrides)
    return await async_client.post("/api/v1/images/edits", json=payload)


async def _artifacts(async_db, run_id: str) -> list[RunArtifact]:
    return list(
        (await async_db.exec(select(RunArtifact).where(RunArtifact.run_id == run_id))).all()
    )


async def _settle(async_client, run_id: str, async_db) -> Run:
    """Let the detached worker finish, then read the run back.

    The task runs on the TestClient's own loop, so a short async hop inside that
    loop is enough; nothing here sleeps against wall-clock time.
    """
    for _ in range(50):
        await async_client.get(f"/api/v1/runs/{run_id}")
        async_db.expire_all()
        run = await async_db.get(Run, run_id)
        if run is not None and run.status in ("succeeded", "failed"):
            return run
    return await async_db.get(Run, run_id)


class TestSynchronousBehaviourIsUnchanged:
    @pytest.mark.asyncio
    async def test_generation_still_returns_images_inline(self, async_client):
        response = await _generate(async_client, n=2)

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()["data"]
        assert body["status"] == "succeeded"
        assert len(body["data"]) == 2
        assert all(image["b64_json"] for image in body["data"])
        assert all(image["attachment_id"] is None for image in body["data"])

    @pytest.mark.asyncio
    async def test_edit_still_returns_images_inline(self, async_client):
        body = (await _edit(async_client)).json()["data"]
        assert body["status"] == "succeeded"
        assert body["data"][0]["b64_json"]


class TestArtifactResponses:
    @pytest.mark.asyncio
    async def test_generated_images_are_written_as_run_artifacts(self, async_client, async_db):
        response = await _generate(async_client, n=2, response_format="artifact")

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()["data"]
        assert len(body["data"]) == 2
        # The bytes moved into governed storage, so the response carries
        # references rather than megabytes of base64.
        assert all(image["attachment_id"] for image in body["data"])
        assert all(image["b64_json"] is None for image in body["data"])

        artifacts = await _artifacts(async_db, body["run_id"])
        assert len(artifacts) == 2
        assert {artifact.id for artifact in artifacts} == {
            image["attachment_id"] for image in body["data"]
        }
        for artifact in artifacts:
            assert artifact.type == "file"
            assert artifact.mime == "image/png"
            assert artifact.size_bytes > 0
            assert len(artifact.sha256) == 64
            assert artifact.meta_json["kind"] == "image"

    @pytest.mark.asyncio
    async def test_artifact_content_is_downloadable(self, async_client, async_db):
        body = (await _generate(async_client, response_format="artifact")).json()["data"]
        artifact_id = body["data"][0]["attachment_id"]

        download = await async_client.get(
            f"/api/v1/runs/{body['run_id']}/artifacts/{artifact_id}/content"
        )
        assert download.status_code == status.HTTP_200_OK, download.json()
        assert download.headers["content-type"].startswith("image/png")
        assert download.content[:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.asyncio
    async def test_edit_artifacts_record_their_operation(self, async_client, async_db):
        body = (await _edit(async_client, response_format="artifact")).json()["data"]

        artifacts = await _artifacts(async_db, body["run_id"])
        assert artifacts[0].meta_json["operation"] == "edit_image"

    @pytest.mark.asyncio
    async def test_webp_output_is_recorded_with_its_own_mime(self, async_client, async_db):
        body = (await _edit(
            async_client, response_format="artifact", output_format="webp"
        )).json()["data"]

        artifacts = await _artifacts(async_db, body["run_id"])
        assert artifacts[0].mime == "image/webp"
        assert artifacts[0].meta_json["name"].endswith(".webp")

    @pytest.mark.asyncio
    async def test_a_webp_generation_is_stored_as_webp(self, async_client, async_db):
        body = (await _generate(
            async_client, response_format="artifact", output_format="webp"
        )).json()["data"]

        [artifact] = await _artifacts(async_db, body["run_id"])
        assert artifact.mime == "image/webp"
        assert artifact.meta_json["name"].endswith(".webp")
        assert "requested_format" not in artifact.meta_json

    @pytest.mark.asyncio
    async def test_an_artifact_is_labelled_by_its_bytes(self, async_client, async_db):
        # A provider that ignores output_format still answers in PNG; the
        # artifact says what it holds, and what was asked for.
        from app.adapters.llm.memory import _TINY_PNG_B64
        from app.kernel.ports.llm.interface import GeneratedImage

        port = _HostedPort([GeneratedImage(b64_json=_TINY_PNG_B64)])
        response = await _with_port(
            port,
            lambda: _generate(async_client, response_format="artifact", output_format="webp"),
        )

        [artifact] = await _artifacts(async_db, response.json()["data"]["run_id"])
        assert artifact.mime == "image/png"
        assert artifact.meta_json["name"] == "0.png"
        assert artifact.meta_json["requested_format"] == "webp"
        content = await async_client.get(
            f"/api/v1/runs/{response.json()['data']['run_id']}/artifacts/{artifact.id}/content"
        )
        assert content.headers["content-type"].startswith("image/png")

    @pytest.mark.asyncio
    async def test_artifacts_still_bill_once(self, async_client, async_db):
        body = (await _generate(async_client, n=2, response_format="artifact")).json()["data"]

        costs = list(
            (await async_db.exec(
                select(RunCostEntry).where(RunCostEntry.run_id == body["run_id"])
            )).all()
        )
        assert len(costs) == 1
        assert costs[0].billed_quantity == 2


class TestAsynchronousJobs:
    @pytest.mark.asyncio
    async def test_generation_returns_a_run_id_before_the_work_finishes(self, async_client, async_db):
        response = await _generate(async_client, n=2, **{"async": True})

        assert response.status_code == status.HTTP_202_ACCEPTED
        body = response.json()["data"]
        assert body["status"] == "queued"
        # Nothing is inlined: the caller polls the run instead of holding a
        # connection open across the provider's latency.
        assert body["data"] == []

        run = await _settle(async_client, body["run_id"], async_db)
        assert run.status == "succeeded"
        # Without a response_format an async job returns as run artifacts:
        # every image it made is there to fetch.
        assert len(await _artifacts(async_db, body["run_id"])) == 2

    @pytest.mark.asyncio
    async def test_async_results_land_as_artifacts(self, async_client, async_db):
        body = (await _generate(
            async_client, n=2, response_format="artifact", **{"async": True}
        )).json()["data"]

        await _settle(async_client, body["run_id"], async_db)
        artifacts = await _artifacts(async_db, body["run_id"])
        assert len(artifacts) == 2
        assert all(artifact.mime == "image/png" for artifact in artifacts)

    @pytest.mark.asyncio
    async def test_async_edits_run_to_completion(self, async_client, async_db):
        response = await _edit(async_client, response_format="artifact", **{"async": True})

        assert response.status_code == status.HTTP_202_ACCEPTED
        body = response.json()["data"]
        run = await _settle(async_client, body["run_id"], async_db)
        assert run.status == "succeeded"
        assert len(await _artifacts(async_db, body["run_id"])) == 1

    @pytest.mark.asyncio
    async def test_async_jobs_still_record_their_cost(self, async_client, async_db):
        body = (await _generate(async_client, n=3, **{"async": True})).json()["data"]

        await _settle(async_client, body["run_id"], async_db)
        costs = list(
            (await async_db.exec(
                select(RunCostEntry).where(RunCostEntry.run_id == body["run_id"])
            )).all()
        )
        assert len(costs) == 1
        assert costs[0].billed_quantity == 3
        assert costs[0].operation == "generate_image"
        # As many images to fetch as were billed.
        assert len(await _artifacts(async_db, body["run_id"])) == 3

    @pytest.mark.asyncio
    async def test_a_failing_async_job_fails_its_run(self, async_client, async_db):
        # A worker that dies quietly would strand the run as "running", and the
        # run is the caller's only signal.
        from app.wiring import get_container

        container = get_container()
        original = container.get("llm_port")

        class _Failing:
            async def generate_image(self, **kwargs: Any):
                raise RuntimeError("Provider is unavailable")

        container.register_singleton("llm_port", _Failing())
        try:
            body = (await _generate(async_client, **{"async": True})).json()["data"]
            run = await _settle(async_client, body["run_id"], async_db)
        finally:
            container.register_singleton("llm_port", original)

        assert run.status == "failed"
        assert run.error_code == "IMAGE_ERROR"


class TestJobRequestContract:
    def test_an_edit_without_an_image_is_rejected_at_construction(self):
        import pytest

        from app.kernel.commons.errors import ValidationError

        with pytest.raises(ValidationError, match="source image"):
            ImageJobRequest(kind="edit", model="model:test:m", prompt="hi")

    def test_an_unknown_kind_is_rejected(self):
        import pytest

        from app.kernel.commons.errors import ValidationError

        with pytest.raises(ValidationError, match="kind"):
            ImageJobRequest(kind="transmute", model="model:test:m", prompt="hi")

    def test_the_summary_records_whether_a_mask_was_used(self):
        request = ImageJobRequest(
            kind="edit", model="model:test:m", prompt="hi", image=b"x", mask=b"y"
        )
        assert "mask=yes" in request.summary
        assert "mask=no" not in request.summary

    def test_artifact_requests_ask_the_provider_for_inline_bytes(self):
        # Providers know nothing about artifacts; that is SOIT's return shape.
        from app.kernel.runtime.images.service import _gateway_kwargs

        request = ImageJobRequest(
            kind="generate",
            model="model:test:m",
            prompt="hi",
            response_format="artifact",
        )
        assert _gateway_kwargs(request, "run_1")["response_format"] == "b64_json"

    def test_output_format_is_sent_only_when_asked_for(self):
        # A generation that names no format leaves the provider its default,
        # so models that do not take the parameter are not handed one.
        from app.kernel.runtime.images.service import _gateway_kwargs

        unset = ImageJobRequest(kind="generate", model="model:test:m", prompt="hi")
        webp = ImageJobRequest(kind="generate", model="model:test:m", prompt="hi", output_format="webp")
        edit = ImageJobRequest(
            kind="edit", model="model:test:m", prompt="hi", image=b"x", output_format="png"
        )
        assert "output_format" not in _gateway_kwargs(unset, "run_1")
        assert _gateway_kwargs(webp, "run_1")["output_format"] == "webp"
        assert _gateway_kwargs(edit, "run_1")["output_format"] == "png"


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        (b"\x89PNG\r\n\x1a\n" + b"\0" * 8, "png"),
        (b"RIFF\0\0\0\0WEBPVP8 ", "webp"),
        (b"\xff\xd8\xff\xe0\0\x10JFIF", "jpeg"),
        (b"GIF89a", None),
        (b"", None),
    ],
)
def test_image_bytes_are_recognised_by_their_signature(image, expected):
    from app.kernel.runtime.images.service import _sniff_format

    assert _sniff_format(image) == expected


def test_detached_worker_survives_a_cancelled_event_loop_reference():
    """The task is held until it finishes.

    asyncio keeps only a weak reference to a bare task, so one that nothing
    points at can be collected mid-flight and its run would never close.
    """
    from app.wiring import image_job

    async def _check() -> int:
        async def _noop() -> None:
            await asyncio.sleep(0)

        task = asyncio.ensure_future(_noop())
        image_job._image_tasks.add(task)
        task.add_done_callback(image_job._image_tasks.discard)
        held = len(image_job._image_tasks)
        await task
        return held

    assert asyncio.run(_check()) == 1



class TestAsyncDelivery:
    """An async job's images reach the caller only as run artifacts."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", ["generate", "edit"])
    @pytest.mark.parametrize("response_format", ["b64_json", "url"])
    async def test_an_inline_format_is_refused_before_anything_is_billed(
        self, async_client, async_db, kind, response_format
    ):
        submit = _generate if kind == "generate" else _edit
        response = await submit(async_client, response_format=response_format, **{"async": True})

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert (await async_db.exec(select(Run).where(Run.mode == "image"))).all() == []
        assert (await async_db.exec(select(RunCostEntry))).all() == []

    @pytest.mark.asyncio
    async def test_an_async_edit_without_a_format_returns_a_downloadable_artifact(
        self, async_client, async_db
    ):
        body = (await _edit(async_client, **{"async": True})).json()["data"]

        run = await _settle(async_client, body["run_id"], async_db)
        [artifact] = await _artifacts(async_db, body["run_id"])
        content = await async_client.get(f"/api/v1/runs/{body['run_id']}/artifacts/{artifact.id}/content")

        assert run.status == "succeeded"
        assert content.status_code == 200
        assert content.headers["content-type"].startswith("image/png")

    @pytest.mark.asyncio
    async def test_polling_the_run_lists_every_billed_image(self, async_client, async_db):
        body = (await _generate(async_client, n=2, **{"async": True})).json()["data"]
        await _settle(async_client, body["run_id"], async_db)

        polled = (await async_client.get(f"/api/v1/runs/{body['run_id']}")).json()["data"]
        [cost] = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == body["run_id"]))).all()

        assert len(polled["artifacts"]) == cost.billed_quantity == 2
        assert all(artifact["meta_json"]["kind"] == "image" for artifact in polled["artifacts"])

    @pytest.mark.asyncio
    async def test_an_image_that_cannot_be_kept_fails_the_job_and_keeps_its_cost(
        self, async_client, async_db
    ):
        from app.kernel.ports.llm.interface import (
            GeneratedImage,
            ImageGenerationResponse,
        )
        from app.wiring import get_container

        container = get_container()
        original = container.get("llm_port")

        class _Empty:
            async def generate_image(self, **kwargs: Any):
                return ImageGenerationResponse(images=[GeneratedImage()], model="m")

        container.register_singleton("llm_port", _Empty())
        try:
            response = await _generate(async_client, response_format="artifact")
        finally:
            container.register_singleton("llm_port", original)

        assert response.status_code == 502
        assert response.json()["code"] == "IMAGE_UNDELIVERABLE"
        [run] = (await async_db.exec(select(Run).where(Run.mode == "image"))).all()
        await async_db.refresh(run)
        assert (run.status, run.error_code) == ("failed", "IMAGE_UNDELIVERABLE")
        # The provider was paid; the ledger says so.
        assert len((await async_db.exec(select(RunCostEntry))).all()) == 1

    @pytest.mark.asyncio
    async def test_the_worker_refuses_a_job_it_could_not_deliver(self, async_client, async_db, ctx):
        from app.kernel.runtime.runs.writer import TraceWriter
        from app.wiring import get_container
        from app.wiring.image_job import run_image_job_detached

        container = get_container()
        original = container.get("llm_port")
        calls: list[dict[str, Any]] = []

        class _Recording:
            async def generate_image(self, **kwargs: Any):
                calls.append(kwargs)
                raise AssertionError("an undeliverable job never reaches the provider")

        run = await TraceWriter(async_db, ctx).create_run("image")
        await async_db.commit()
        container.register_singleton("llm_port", _Recording())
        try:
            await run_image_job_detached(
                bind=async_db.bind,
                ctx=ctx,
                request=ImageJobRequest(kind="generate", model="model:test:m", prompt="hi"),
                run_id=run.id,
            )
        finally:
            container.register_singleton("llm_port", original)

        await async_db.refresh(run)
        assert run.status == "failed"
        assert calls == []



_HOSTED = "https://provider.example/images/0.png?signature=abc"


class _HostedPort:
    """A provider that keeps the bytes and answers with where they are."""

    def __init__(self, images):
        self.images = images

    async def generate_image(self, **kwargs: Any):
        from app.kernel.ports.llm.interface import ImageGenerationResponse

        return ImageGenerationResponse(images=list(self.images), model="m")


async def _with_port(port, call):
    from app.wiring import get_container

    container = get_container()
    original = container.get("llm_port")
    container.register_singleton("llm_port", port)
    try:
        return await call()
    finally:
        container.register_singleton("llm_port", original)


class TestProviderHostedResults:
    """A provider that answers with a URL still leaves the run something to fetch."""

    @pytest.mark.asyncio
    async def test_an_async_url_only_result_becomes_a_link_artifact(self, async_client, async_db):
        from app.kernel.ports.llm.interface import GeneratedImage

        port = _HostedPort([GeneratedImage(url=_HOSTED)])

        async def submit_and_settle():
            body = (await _generate(async_client, **{"async": True})).json()["data"]
            return body, await _settle(async_client, body["run_id"], async_db)

        body, run = await _with_port(port, submit_and_settle)

        assert run.status == "succeeded"
        [artifact] = await _artifacts(async_db, body["run_id"])
        assert artifact.type == "json"
        assert artifact.mime == "application/json"
        assert artifact.meta_json["kind"] == "image_url"
        assert artifact.meta_json["inspected"] is False
        # The link may be signed: it lives in the object, not in what listings show.
        assert _HOSTED not in str(artifact.meta_json)
        content = await async_client.get(
            f"/api/v1/runs/{body['run_id']}/artifacts/{artifact.id}/content"
        )
        assert content.status_code == 200
        # JSON content comes back in the API envelope, as every JSON body does.
        assert content.json()["data"] == {"index": 0, "url": _HOSTED}

    @pytest.mark.asyncio
    async def test_a_synchronous_artifact_answer_carries_the_url_and_the_link(
        self, async_client, async_db
    ):
        from app.kernel.ports.llm.interface import GeneratedImage

        port = _HostedPort([GeneratedImage(url=_HOSTED)])
        response = await _with_port(
            port, lambda: _generate(async_client, response_format="artifact")
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        [datum] = response.json()["data"]["data"]
        [artifact] = await _artifacts(async_db, response.json()["data"]["run_id"])
        assert datum["url"] == _HOSTED
        assert datum["attachment_id"] == artifact.id

    @pytest.mark.asyncio
    async def test_every_billed_image_of_a_mixed_answer_is_kept(self, async_client, async_db):
        from app.adapters.llm.memory import _TINY_PNG_B64
        from app.kernel.ports.llm.interface import GeneratedImage

        port = _HostedPort([GeneratedImage(b64_json=_TINY_PNG_B64), GeneratedImage(url=_HOSTED)])
        response = await _with_port(
            port, lambda: _generate(async_client, n=2, response_format="artifact")
        )

        run_id = response.json()["data"]["run_id"]
        [cost] = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id))).all()
        artifacts = sorted(await _artifacts(async_db, run_id), key=lambda a: a.meta_json["index"])
        assert [a.meta_json["kind"] for a in artifacts] == ["image", "image_url"]
        assert len(artifacts) == cost.billed_quantity == 2

@pytest.mark.parametrize(
    ("requested", "detached", "resolved"),
    [
        (None, False, "b64_json"),
        ("url", False, "url"),
        ("artifact", False, "artifact"),
        (None, True, "artifact"),
        ("artifact", True, "artifact"),
    ],
)
def test_a_response_format_resolves_to_what_can_be_delivered(requested, detached, resolved):
    from app.kernel.runtime.images.service import resolve_response_format

    assert resolve_response_format(requested, detached=detached) == resolved


@pytest.mark.parametrize("requested", ["b64_json", "url", "gif"])
def test_a_detached_job_refuses_anything_but_artifacts(requested):
    from app.kernel.commons.errors import ValidationError
    from app.kernel.runtime.images.service import resolve_response_format

    with pytest.raises(ValidationError):
        resolve_response_format(requested, detached=True)


class TestUndeliverableImages:
    """A billed image SOIT cannot keep fails the job under IMAGE_UNDELIVERABLE."""

    @pytest.mark.asyncio
    async def test_an_async_job_says_so_on_its_run(self, async_client, async_db):
        from app.kernel.ports.llm.interface import GeneratedImage

        port = _HostedPort([GeneratedImage()])

        async def submit_and_settle():
            body = (await _generate(async_client, **{"async": True})).json()["data"]
            return body, await _settle(async_client, body["run_id"], async_db)

        body, run = await _with_port(port, submit_and_settle)

        # Polling the run is all an async caller has.
        assert (run.status, run.error_code) == ("failed", "IMAGE_UNDELIVERABLE")
        costs = (await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == body["run_id"]))).all()
        assert len(costs) == 1

    @pytest.mark.asyncio
    async def test_an_undecodable_image_is_the_providers_fault(self, async_client, async_db):
        from app.kernel.ports.llm.interface import GeneratedImage

        port = _HostedPort([GeneratedImage(b64_json="!!! not base64 !!!")])
        response = await _with_port(
            port, lambda: _generate(async_client, response_format="artifact")
        )

        assert response.status_code == 502, response.text
        assert response.json()["code"] == "IMAGE_UNDELIVERABLE"
        [run] = (await async_db.exec(select(Run).where(Run.mode == "image"))).all()
        await async_db.refresh(run)
        assert (run.status, run.error_code) == ("failed", "IMAGE_UNDELIVERABLE")
        assert len((await async_db.exec(select(RunCostEntry))).all()) == 1
