"""LiteLLM adapter behaviour for governed image edits (M1).

The in-memory port cannot show these: whether the mask is converted for the
provider that needs it, and whether parameters outside the OpenAI edit shape
reach the provider instead of being dropped.
"""

import io
from typing import Any

import pytest
from PIL import Image

from app.adapters.llm.litellm import LiteLLMPort
from app.kernel.commons.errors import ValidationError


def _mask_png(size=(8, 8)) -> bytes:
    """Left half white: the region to edit under SOIT's convention."""
    mask = Image.new("L", size, 0)
    for x in range(size[0] // 2):
        for y in range(size[1]):
            mask.putpixel((x, y), 255)
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return buffer.getvalue()


class _Recorder:
    """Stands in for litellm.aimage_edit and keeps what it was called with."""

    def __init__(self) -> None:
        self.params: dict[str, Any] | None = None

    async def __call__(self, **params: Any):
        self.params = params
        return {
            "data": [{"b64_json": "aGk="}],
            "model": params.get("model"),
        }


def _port(provider_kind: str, recorder: _Recorder) -> LiteLLMPort:
    return LiteLLMPort(
        provider_kind=provider_kind,
        api_key="test-key",
        completion_fn=_Recorder(),
        embedding_fn=_Recorder(),
        image_generation_fn=_Recorder(),
        image_edit_fn=recorder,
        load_sdk_defaults=False,
    )


class TestMaskConversion:
    @pytest.mark.asyncio
    async def test_openai_receives_an_alpha_mask(self):
        # OpenAI reads only alpha, where transparent marks the region to
        # replace. Sending our white-is-edit mask unchanged would invert it.
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
            mask=_mask_png(),
        )

        with Image.open(io.BytesIO(recorder.params["mask"])) as sent:
            assert sent.mode == "RGBA"
            alpha = sent.getchannel("A")
            assert alpha.getpixel((0, 0)) == 0
            assert alpha.getpixel((7, 0)) == 255

    @pytest.mark.asyncio
    async def test_other_providers_receive_the_mask_unchanged(self):
        # Stable Diffusion style providers already read white as the edit
        # region, so converting would invert it for them instead.
        recorder = _Recorder()
        original = _mask_png()
        await _port("bedrock", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:bedrock:stability",
            mask=original,
        )
        assert recorder.params["mask"] == original

    @pytest.mark.asyncio
    async def test_no_mask_sends_no_mask(self):
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
        )
        assert "mask" not in recorder.params


class TestRequestShape:
    @pytest.mark.asyncio
    async def test_core_parameters_are_forwarded(self):
        # dall-e-2 rather than gpt-image, because gpt-image rejects
        # response_format outright; that case is covered on its own below.
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:dall-e-2",
            n=3,
            size="1024x1024",
        )
        assert recorder.params["image"] == b"image-bytes"
        assert recorder.params["prompt"] == "a red dot"
        assert recorder.params["n"] == 3
        assert recorder.params["size"] == "1024x1024"
        assert recorder.params["response_format"] == "b64_json"

    @pytest.mark.asyncio
    async def test_non_standard_parameters_travel_in_extra_body(self):
        # Dropping a seed would make a request the caller believes is
        # reproducible quietly not be.
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
            seed=42,
            strength=0.5,
            negative_prompt="blurry",
        )
        extra = recorder.params["extra_body"]
        assert extra["seed"] == 42
        assert extra["strength"] == 0.5
        assert extra["negative_prompt"] == "blurry"

    @pytest.mark.asyncio
    async def test_unset_parameters_are_not_invented(self):
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
        )
        assert "extra_body" not in recorder.params

    @pytest.mark.asyncio
    async def test_response_is_mapped_to_the_kernel_shape(self):
        recorder = _Recorder()
        response = await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
        )
        assert len(response.images) == 1
        assert response.images[0].b64_json == "aGk="

    @pytest.mark.asyncio
    async def test_missing_gateway_capability_is_reported_plainly(self):
        port = LiteLLMPort(
            provider_kind="openai",
            api_key="test-key",
            completion_fn=_Recorder(),
            embedding_fn=_Recorder(),
            image_generation_fn=_Recorder(),
            image_edit_fn=None,
            load_sdk_defaults=False,
        )
        with pytest.raises(ValidationError, match="image editing"):
            await port.edit_image(
                image=b"image-bytes",
                prompt="a red dot",
                model="model:openai:gpt-image-1",
            )


class TestResponseFormatCompatibility:
    """Regression: found against real gpt-image-1 credentials.

    The model always answers with inline base64 and rejects the parameter that
    asks for it, while LiteLLM still lists response_format among its supported
    params. Sending it made every gpt-image call fail at the provider with
    "Unknown parameter: 'response_format'".
    """

    def test_gpt_image_models_do_not_accept_the_parameter(self):
        for model in (
            "openai/gpt-image-1",
            "openai/gpt-image-1.5",
            "gpt-image-2",
            "openai/chatgpt-image-latest",
        ):
            assert LiteLLMPort._accepts_response_format(model) is False, model

    def test_other_image_models_still_accept_it(self):
        for model in ("openai/dall-e-2", "openai/dall-e-3", "bedrock/stability"):
            assert LiteLLMPort._accepts_response_format(model) is True, model

    @pytest.mark.asyncio
    async def test_the_parameter_is_omitted_for_gpt_image_edits(self):
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
        )
        assert "response_format" not in recorder.params

    @pytest.mark.asyncio
    async def test_the_parameter_is_sent_where_it_is_understood(self):
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:dall-e-2",
        )
        assert recorder.params["response_format"] == "b64_json"

    @pytest.mark.asyncio
    async def test_generation_omits_it_for_gpt_image_too(self):
        # The same latent failure existed on the generation path.
        recorder = _Recorder()
        port = LiteLLMPort(
            provider_kind="openai",
            api_key="test-key",
            completion_fn=_Recorder(),
            embedding_fn=_Recorder(),
            image_generation_fn=recorder,
            image_edit_fn=_Recorder(),
            load_sdk_defaults=False,
        )
        await port.generate_image(prompt="a red dot", model="model:openai:gpt-image-1")
        assert "response_format" not in recorder.params

    @pytest.mark.asyncio
    async def test_a_url_request_is_refused_rather_than_silently_changed(self):
        # Handing back base64 under a URL request would break the response
        # shape the caller coded against.
        recorder = _Recorder()
        with pytest.raises(ValidationError, match="inline image bytes only"):
            await _port("openai", recorder).edit_image(
                image=b"image-bytes",
                prompt="a red dot",
                model="model:openai:gpt-image-1",
                response_format="url",
            )
