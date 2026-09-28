"""What the LiteLLM adapter's image options put on the wire.

Recorder tests show where the adapter places an option; only the request that
leaves LiteLLM shows whether the provider receives it, because LiteLLM drops
what it does not map without raising. These run the real SDK against a mock
transport, so a LiteLLM upgrade that changes the mapping fails here rather
than in a caller's opaque image.
"""

import contextlib
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
    def __init__(self, answer: dict[str, Any] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.answer = answer or {"created": 1, "data": [{"b64_json": "aGk="}]}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.answer)

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

    def file(self, name: str) -> bytes:
        """The bytes of the multipart file part called name."""
        request = self.requests[-1]
        boundary = request.headers["content-type"].split("boundary=", 1)[1].strip('"')
        for part in request.content.split(b"--" + boundary.encode()):
            head, separator, content = part.partition(b"\r\n\r\n")
            if separator and f'name="{name}"'.encode() in head:
                return content.removesuffix(b"\r\n")
        raise AssertionError(f"no {name} part on the wire")


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="PNG")
    return buffer.getvalue()


def _left_half_mask() -> bytes:
    """SOIT's convention: white, here the left half, is the region to edit."""
    mask = Image.new("L", (8, 8), 0)
    mask.paste(255, (0, 0, 4, 8))
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


def _port(
    wire: _Wire,
    litellm_provider: str | None = None,
    *,
    provider_kind: str = "openai",
    **litellm_params: Any,
) -> LiteLLMPort:
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
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
        api_key="test-key",
        api_base=_API_BASE,
        litellm_params=litellm_params,
        image_generation_fn=functools.partial(litellm.aimage_generation, client=openai_client),
        image_edit_fn=functools.partial(litellm.aimage_edit, client=edit_client),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "litellm_provider", "litellm_params"),
    [
        ("openai:gpt-image-1", None, {}),
        # LiteLLM refuses response_format for this model unless told to drop it.
        ("openai:doubao-seedream-3-0", None, {"drop_params": True}),
        # A provider LiteLLM treats as OpenAI-compatible drops them as plain
        # arguments just the same.
        ("litellm_proxy:gpt-image-1", "litellm_proxy", {}),
    ],
)
async def test_a_generation_sends_background_and_output_format(model, litellm_provider, litellm_params):
    wire = _Wire()
    await _port(wire, litellm_provider, **litellm_params).generate_image(
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
async def test_an_edit_sends_its_seed_where_litellm_reads_it():
    # LiteLLM's Stability edit takes the options as plain arguments; an edit
    # never sends extra_body.
    wire = _Wire()
    with contextlib.suppress(Exception):
        # The mock answers in OpenAI's shape, which Stability's parser refuses
        # after the request has been captured.
        await _port(wire, litellm_provider="stability").edit_image(
            image=_png(),
            prompt="a red dot",
            model="model:stability:sd3-large",
            seed=42,
            negative_prompt="blurry",
        )

    assert wire.requests, "the edit reached the wire"
    body = wire.requests[-1].content
    assert b'name="seed"' in body and b"42" in body
    assert b'name="negative_prompt"' in body


@pytest.mark.asyncio
async def test_stability_receives_a_mask_whose_white_marks_the_edit():
    # An OpenAI-compatible provider routed to Stability, as an operator
    # configures one: the kind cannot say Stability, the LiteLLM prefix does.
    # Stability reads the mask's luminance, white repainted and black kept.
    wire = _Wire({"image": "aGk=", "finish_reason": "SUCCESS", "seed": 1})
    await _port(wire, "stability", provider_kind="openai_compatible").edit_image(
        image=_png(),
        prompt="a red dot",
        model="model:stability:inpaint",
        mask=_left_half_mask(),
    )

    assert wire.requests[-1].url.path.endswith("/stable-image/edit/inpaint")
    with Image.open(io.BytesIO(wire.file("mask"))) as sent:
        luminance = sent.convert("L")
    assert luminance.getpixel((0, 0)) == 255
    assert luminance.getpixel((3, 7)) == 255
    assert luminance.getpixel((4, 0)) == 0
    assert luminance.getpixel((7, 7)) == 0


@pytest.mark.asyncio
async def test_an_openai_compatible_edit_receives_a_mask_whose_transparency_marks_the_edit():
    wire = _Wire()
    await _port(wire, provider_kind="openai_compatible").edit_image(
        image=_png(),
        prompt="a red dot",
        model="model:gateway:gpt-image-1",
        mask=_left_half_mask(),
    )

    with Image.open(io.BytesIO(wire.file("mask"))) as sent:
        alpha = sent.getchannel("A")
    assert alpha.getpixel((0, 0)) == 0
    assert alpha.getpixel((3, 7)) == 0
    assert alpha.getpixel((4, 0)) == 255
    assert alpha.getpixel((7, 7)) == 255
