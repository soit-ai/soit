"""What the LiteLLM adapter's image options put on the wire.

Recorder tests show where the adapter places an option; only the request that
leaves LiteLLM shows whether the provider receives it, because LiteLLM drops
what it does not map without raising. These run the real SDK against a mock
transport, so a LiteLLM upgrade that changes the mapping fails here rather
than in a caller's opaque image.
"""

import functools
import io
import json
import re
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from app.adapters.llm.litellm import LiteLLMPort

_API_BASE = "https://provider.test/v1"


class _Wire:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"created": 1, "data": [{"b64_json": "aGk="}]})

    @property
    def json(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)

    @property
    def form(self) -> dict[str, str]:
        body = self.requests[-1].content
        return {
            name.decode(): value.decode(errors="replace")
            for name, value in re.findall(rb'name="([^"]+)"\r\n\r\n(.*?)\r\n--', body, re.S)
        }


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="PNG")
    return buffer.getvalue()


def _port(wire: _Wire, **litellm_params: Any) -> LiteLLMPort:
    import litellm
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

    openai_client = AsyncOpenAI(
        api_key="test-key",
        base_url=_API_BASE,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(wire)),
    )
    # Image edits go through LiteLLM's own HTTP handler, not the OpenAI SDK.
    edit_client = AsyncHTTPHandler()
    edit_client.client = httpx.AsyncClient(transport=httpx.MockTransport(wire))
    return LiteLLMPort(
        provider_kind="openai",
        api_key="test-key",
        api_base=_API_BASE,
        litellm_params=litellm_params,
        image_generation_fn=functools.partial(litellm.aimage_generation, client=openai_client),
        image_edit_fn=functools.partial(litellm.aimage_edit, client=edit_client),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "litellm_params"),
    [
        ("openai:gpt-image-1", {}),
        # LiteLLM refuses response_format for this model unless told to drop it.
        ("openai:doubao-seedream-3-0", {"drop_params": True}),
    ],
)
async def test_a_generation_sends_background_and_output_format(model, litellm_params):
    wire = _Wire()
    await _port(wire, **litellm_params).generate_image(
        prompt="a red dot",
        model=f"model:{model}",
        background="transparent",
        output_format="webp",
    )

    assert wire.json["background"] == "transparent"
    assert wire.json["output_format"] == "webp"


@pytest.mark.asyncio
async def test_a_generation_sends_no_option_it_was_not_given():
    wire = _Wire()
    await _port(wire).generate_image(prompt="a red dot", model="model:openai:dall-e-3")

    assert "background" not in wire.json
    assert "output_format" not in wire.json


@pytest.mark.asyncio
async def test_an_edit_sends_background():
    wire = _Wire()
    await _port(wire).edit_image(
        image=_png(),
        prompt="a red dot",
        model="model:openai:gpt-image-1",
        background="transparent",
    )

    assert wire.form["background"] == "transparent"


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    reason="LiteLLM's edit request discards extra_body on OpenAI-style providers",
)
async def test_an_edit_sends_its_seed():
    wire = _Wire()
    await _port(wire).edit_image(
        image=_png(),
        prompt="a red dot",
        model="model:openai:gpt-image-1",
        seed=42,
    )

    assert wire.form["seed"] == "42"
