"""An image option the model's LiteLLM route cannot carry is refused before a run opens.

These drive the real LiteLLM adapter behind both image surfaces, with LiteLLM
itself replaced by a recorder, so the route table decides: an option the route
has no place for is refused with 422 before anything is opened, admitted or
billed, for a synchronous call and an asynchronous job alike, and what the
route carries still goes through.
"""

from __future__ import annotations

import base64
import io
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import status
from PIL import Image
from sqlmodel import select

from app.adapters.llm.litellm import LiteLLMPort
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.wiring import get_container

MODEL = "model:openai:gpt-image-1"


def _png(size: tuple[int, int] = (64, 64), mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, (10, 20, 30) if mode == "RGB" else 0).save(buffer, format="PNG")
    return buffer.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class _LiteLLM:
    """Stands in for litellm.aimage_generation / aimage_edit."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **params: Any) -> dict[str, Any]:
        self.calls.append(params)
        count = params.get("n", 1)
        return {"data": [{"b64_json": _b64(_png())} for _ in range(count)], "model": params["model"]}


@pytest.fixture
def litellm_calls() -> Iterator[_LiteLLM]:
    recorder = _LiteLLM()
    port = LiteLLMPort(
        provider_kind="openai",
        api_key="sk-test",
        completion_fn=_LiteLLM(),
        embedding_fn=_LiteLLM(),
        image_generation_fn=recorder,
        image_edit_fn=recorder,
        load_sdk_defaults=False,
    )
    container = get_container()
    original = container.get("llm_port")
    container.register_singleton("llm_port", port)
    try:
        yield recorder
    finally:
        container.register_singleton("llm_port", original)


async def _nothing_opened(async_db) -> None:
    assert (await async_db.exec(select(Run).where(Run.kind == "image"))).all() == []
    assert (await async_db.exec(select(RunCostEntry))).all() == []


class TestNativeImages:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("run_async", [False, True])
    async def test_a_seed_the_openai_edit_cannot_carry_is_refused_before_a_run(
        self, async_client, async_db, litellm_calls, run_async
    ) -> None:
        response = await async_client.post(
            "/api/v1/images/edits",
            json={
                "model": MODEL,
                "prompt": "a red dot",
                "image_b64": _b64(_png()),
                "seed": 7,
                "async": run_async,
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
        body = response.json()
        assert body["code"] == "MODEL_IMAGE_CAPABILITY_UNAVAILABLE"
        assert body["details"]["reason"] == "route_cannot_carry"
        assert body["details"]["param"] == "seed"
        assert litellm_calls.calls == []
        await _nothing_opened(async_db)

    @pytest.mark.asyncio
    async def test_more_images_than_the_route_returns_is_refused_with_the_limit(
        self, async_client, async_db, litellm_calls
    ) -> None:
        # Asked of a route that sends no count, the call would answer with one.
        port = get_container().get("llm_port")
        port.litellm_provider = "stability"

        response = await async_client.post(
            "/api/v1/images/generations",
            json={"model": "model:stability:sd3-large", "prompt": "a red dot", "n": 2},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
        assert response.json()["details"]["max_n"] == 1
        await _nothing_opened(async_db)

    @pytest.mark.asyncio
    async def test_an_edit_the_route_carries_goes_through(self, async_client, litellm_calls) -> None:
        # The shape Picover sends: png asked for, a transparent background, a
        # mask and more than one image.
        response = await async_client.post(
            "/api/v1/images/edits",
            json={
                "model": MODEL,
                "prompt": "a red dot",
                "image_b64": _b64(_png()),
                "mask_b64": _b64(_png(mode="L")),
                "n": 2,
                "background": "transparent",
                "output_format": "png",
                "response_format": "b64_json",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        (sent,) = litellm_calls.calls
        assert sent["n"] == 2
        assert sent["background"] == "transparent"
        assert "mask" in sent
        # OpenAI's edit answers in PNG and has no field for the format.
        assert "output_format" not in sent

    @pytest.mark.asyncio
    async def test_an_edit_asking_for_no_format_is_sent_none(self, async_client, litellm_calls) -> None:
        response = await async_client.post(
            "/api/v1/images/edits",
            json={"model": MODEL, "prompt": "a red dot", "image_b64": _b64(_png())},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert "output_format" not in litellm_calls.calls[0]


class TestOpenAICompatibleImages:
    @pytest.mark.asyncio
    async def test_a_format_the_openai_edit_cannot_carry_is_refused_by_name(
        self, async_client, async_db, litellm_calls
    ) -> None:
        response = await async_client.post(
            "/v1/images/edits",
            files={"image": ("source.png", _png(), "image/png")},
            data={"model": MODEL, "prompt": "fill it", "output_format": "webp"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
        error = response.json()["error"]
        assert error["type"] == "invalid_request_error"
        assert error["param"] == "output_format"
        assert "x-soit-run-id" not in response.headers
        assert litellm_calls.calls == []
        await _nothing_opened(async_db)

    @pytest.mark.asyncio
    async def test_a_background_the_generation_carries_goes_through(self, async_client, litellm_calls) -> None:
        response = await async_client.post(
            "/v1/images/generations",
            json={"model": MODEL, "prompt": "a red dot", "background": "transparent", "output_format": "webp"},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert litellm_calls.calls[0]["extra_body"] == {"background": "transparent", "output_format": "webp"}


class TestTheCheckBeforeTheRun:
    """Each part of the request reaches the check made before the run opens."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("litellm_provider", "path", "body", "param"),
        [
            # Gemini's Imagen edit has no mask to send.
            (
                "gemini",
                "/api/v1/images/edits",
                {
                    "model": "model:gemini:imagen-4.0-generate-001",
                    "image_b64": _b64(_png()),
                    "mask_b64": _b64(_png(mode="L")),
                },
                "mask",
            ),
            # Bedrock's SD3 generation refuses any size.
            (
                "bedrock",
                "/api/v1/images/generations",
                {"model": "model:bedrock:stability.sd3-large-v1:0", "size": "1024x1024"},
                "size",
            ),
        ],
    )
    async def test_an_async_job_is_refused_before_it_is_accepted(
        self, async_client, async_db, litellm_calls, litellm_provider, path, body, param
    ) -> None:
        get_container().get("llm_port").litellm_provider = litellm_provider

        response = await async_client.post(path, json={"prompt": "a red dot", "async": True, **body})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
        assert response.json()["details"]["param"] == param
        assert litellm_calls.calls == []
        await _nothing_opened(async_db)

    @pytest.mark.asyncio
    async def test_a_url_the_route_cannot_return_is_refused_before_a_run(
        self, async_client, async_db, litellm_calls
    ) -> None:
        response = await async_client.post(
            "/api/v1/images/generations",
            json={"model": MODEL, "prompt": "a red dot", "response_format": "url"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert litellm_calls.calls == []
        await _nothing_opened(async_db)
