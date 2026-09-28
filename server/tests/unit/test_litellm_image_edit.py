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
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.runtime_config import image_takes_response_format


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


def _port(
    provider_kind: str,
    recorder: _Recorder,
    litellm_provider: str | None = None,
) -> LiteLLMPort:
    return LiteLLMPort(
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
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
            model="model:bedrock:stability.stable-image-inpaint-v1:0",
            mask=original,
        )
        assert recorder.params["mask"] == original

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("provider_kind", "litellm_provider", "model"),
        [
            ("openai_compatible", None, "model:gateway:gpt-image-1"),
            ("azure_openai", None, "model:azure:gpt-image-1"),
            # LiteLLM's edit request for these reuses its OpenAI one, which
            # passes the mask to an OpenAI-style endpoint untouched.
            ("openai_compatible", "azure_ai", "model:foundry:flux.1-kontext-pro"),
            ("openai_compatible", "litellm_proxy", "model:proxy:gpt-image-1"),
        ],
    )
    async def test_openai_style_routes_receive_an_alpha_mask(
        self, provider_kind, litellm_provider, model
    ):
        recorder = _Recorder()
        await _port(provider_kind, recorder, litellm_provider).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model=model,
            mask=_mask_png(),
        )

        with Image.open(io.BytesIO(recorder.params["mask"])) as sent:
            assert sent.mode == "RGBA"
            alpha = sent.getchannel("A")
            assert alpha.getpixel((0, 0)) == 0
            assert alpha.getpixel((7, 0)) == 255

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("provider_kind", "litellm_provider", "model"),
        [
            # The kind says OpenAI, but LiteLLM routes on the prefix and sends
            # the edit to Stability. Stability reads luminance, so an alpha
            # mask, black in every pixel, would select nothing.
            ("openai_compatible", "stability", "model:stability:inpaint"),
            ("openai", "stability", "model:stability:sd3-large"),
            ("bedrock", None, "model:bedrock:stability.stable-image-inpaint-v1:0"),
            ("openai_compatible", "vertex_ai", "model:vertex:imagen-3.0-capability-001"),
        ],
    )
    async def test_luminance_routes_receive_the_white_is_edit_mask(
        self, provider_kind, litellm_provider, model
    ):
        recorder = _Recorder()
        original = _mask_png()
        await _port(provider_kind, recorder, litellm_provider).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model=model,
            mask=original,
        )

        assert recorder.params["mask"] == original

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("litellm_provider", "model", "code", "reason"),
        [
            # LiteLLM's Black Forest Labs edit maps its options through a list
            # without the mask, so even its fill model is sent none.
            (
                "black_forest_labs",
                "model:bfl:flux-pro-1.0-fill",
                "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
                "route_cannot_carry",
            ),
            # A prefix LiteLLM has no edit request for cannot edit at all.
            ("in_house", "model:in_house:painter", "MODEL_CAPABILITY_UNAVAILABLE", "no_litellm_route"),
        ],
    )
    async def test_a_mask_no_route_carries_is_refused(self, litellm_provider, model, code, reason):
        recorder = _Recorder()
        with pytest.raises(KernelError) as refused:
            await _port("openai_compatible", recorder, litellm_provider).edit_image(
                image=b"image-bytes",
                prompt="a red dot",
                model=model,
                mask=_mask_png(),
            )

        assert refused.value.code == code
        assert refused.value.details["reason"] == reason
        assert recorder.params is None

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
    async def test_non_standard_parameters_are_plain_arguments(self):
        # LiteLLM sends no edit's extra_body; its Bedrock, Stability and BFL
        # edits read plain arguments.
        recorder = _Recorder()
        await _port("openai_compatible", recorder, "stability").edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:stability:sd3-large",
            seed=42,
            strength=0.5,
            negative_prompt="blurry",
        )
        assert recorder.params["seed"] == 42
        assert recorder.params["strength"] == 0.5
        assert recorder.params["negative_prompt"] == "blurry"
        assert "extra_body" not in recorder.params

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", ["seed", "strength", "negative_prompt"])
    async def test_an_option_the_openai_edit_drops_is_refused(self, name):
        # LiteLLM's OpenAI-style edit request has no field for it, so the
        # provider would never see it while the edit was billed.
        recorder = _Recorder()
        value = {"seed": 42, "strength": 0.5, "negative_prompt": "blurry"}[name]
        with pytest.raises(KernelError) as refused:
            await _port("openai", recorder).edit_image(
                image=b"image-bytes",
                prompt="a red dot",
                model="model:openai:gpt-image-1",
                **{name: value},
            )

        assert refused.value.code == "MODEL_IMAGE_CAPABILITY_UNAVAILABLE"
        assert refused.value.details == {
            "model": "model:openai:gpt-image-1",
            "capability": name,
            "param": name,
            "reason": "route_cannot_carry",
            "route": "OpenAIImageEditConfig",
        }
        # The message names the option, never the value.
        assert "blurry" not in refused.value.message
        assert recorder.params is None

    @pytest.mark.asyncio
    async def test_background_is_a_plain_argument(self):
        # LiteLLM's edit request keeps background from its own argument list
        # and discards extra_body on OpenAI-style providers.
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
            background="transparent",
        )
        assert recorder.params["background"] == "transparent"
        assert "extra_body" not in recorder.params

    @pytest.mark.asyncio
    async def test_unset_parameters_are_not_invented(self):
        recorder = _Recorder()
        await _port("openai", recorder).edit_image(
            image=b"image-bytes",
            prompt="a red dot",
            model="model:openai:gpt-image-1",
        )
        assert "extra_body" not in recorder.params
        assert "background" not in recorder.params

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


class TestGenerationOptions:
    """Options outside LiteLLM's generation mapping travel in extra_body."""

    @staticmethod
    def _generation_port(recorder: _Recorder) -> LiteLLMPort:
        return LiteLLMPort(
            provider_kind="openai",
            api_key="test-key",
            completion_fn=_Recorder(),
            embedding_fn=_Recorder(),
            image_generation_fn=recorder,
            image_edit_fn=_Recorder(),
            load_sdk_defaults=False,
        )

    @pytest.mark.asyncio
    async def test_background_and_output_format_travel_in_extra_body(self):
        # As plain arguments LiteLLM drops them for gpt-image without a word.
        recorder = _Recorder()
        await self._generation_port(recorder).generate_image(
            prompt="a red dot",
            model="model:openai:gpt-image-1",
            background="transparent",
            output_format="webp",
        )
        assert recorder.params["extra_body"] == {"background": "transparent", "output_format": "webp"}
        assert "background" not in recorder.params
        assert "output_format" not in recorder.params

    @pytest.mark.asyncio
    async def test_unset_options_are_not_invented(self):
        recorder = _Recorder()
        await self._generation_port(recorder).generate_image(
            prompt="a red dot",
            model="model:openai:dall-e-3",
        )
        assert "extra_body" not in recorder.params

    @pytest.mark.asyncio
    async def test_other_providers_take_them_as_plain_arguments(self):
        # Elsewhere LiteLLM forwards extra_body as a field of that name, so
        # a route that maps the options, such as Gemini's Imagen, takes them
        # as plain arguments.
        recorder = _Recorder()
        port = LiteLLMPort(
            provider_kind="gemini",
            api_key="test-key",
            completion_fn=_Recorder(),
            embedding_fn=_Recorder(),
            image_generation_fn=recorder,
            image_edit_fn=_Recorder(),
            load_sdk_defaults=False,
        )
        await port.generate_image(
            prompt="a red dot",
            model="model:gemini:imagen-4.0-generate-001",
            background="transparent",
            output_format="webp",
        )
        assert (recorder.params["background"], recorder.params["output_format"]) == ("transparent", "webp")
        assert "extra_body" not in recorder.params


class TestResponseFormatCompatibility:
    """Regression: found against real gpt-image-1 credentials.

    The model always answers with inline base64 and rejects the parameter that
    asks for it, while LiteLLM still lists response_format among its supported
    params. Sending it made every gpt-image call fail at the provider with
    "Unknown parameter: 'response_format'".
    """

    @pytest.mark.parametrize("operation", ["generate", "edit"])
    def test_gpt_image_models_do_not_accept_the_parameter(self, operation):
        for model in (
            "openai/gpt-image-1",
            "openai/gpt-image-1.5",
            "gpt-image-2",
            "openai/chatgpt-image-latest",
        ):
            assert image_takes_response_format(None, model=model, operation=operation) is False

    @pytest.mark.parametrize("operation", ["generate", "edit"])
    def test_other_image_models_still_accept_it(self, operation):
        for model in ("openai/dall-e-2", "openai/dall-e-3", "bedrock/stability"):
            assert image_takes_response_format(None, model=model, operation=operation) is True

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
        with pytest.raises(ValidationError, match="cannot be asked for a URL"):
            await _port("openai", recorder).edit_image(
                image=b"image-bytes",
                prompt="a red dot",
                model="model:openai:gpt-image-1",
                response_format="url",
            )


class TestDeclaredResponseFormatParameter:
    """Whether an endpoint takes response_format is the model's declared trait.

    Picover met dall-e-2 refusing it on /images/edits while its generations
    took it: the constraint is the endpoint's, which a model name cannot say.
    """

    @staticmethod
    def _declared_port(declared, generate: _Recorder, edit: _Recorder) -> LiteLLMPort:
        return LiteLLMPort(
            provider_kind="openai",
            api_key="test-key",
            completion_fn=_Recorder(),
            embedding_fn=_Recorder(),
            image_generation_fn=generate,
            image_edit_fn=edit,
            load_sdk_defaults=False,
            image_capabilities={"response_format_param": declared},
        )

    @pytest.mark.asyncio
    async def test_an_edit_declared_without_it_is_not_sent_it(self):
        generate, edit = _Recorder(), _Recorder()
        port = self._declared_port({"generate": True, "edit": False}, generate, edit)

        await port.generate_image(prompt="a red dot", model="model:openai:dall-e-2")
        await port.edit_image(image=b"image-bytes", prompt="a red dot", model="model:openai:dall-e-2")

        assert generate.params["response_format"] == "b64_json"
        assert "response_format" not in edit.params

    @pytest.mark.asyncio
    async def test_a_declaration_overrides_the_gpt_image_default(self):
        generate, edit = _Recorder(), _Recorder()
        port = self._declared_port({"generate": True, "edit": None}, generate, edit)

        await port.generate_image(prompt="a red dot", model="model:openai:gpt-image-9", response_format="url")
        await port.edit_image(image=b"image-bytes", prompt="a red dot", model="model:openai:gpt-image-9")

        assert generate.params["response_format"] == "url"
        # Undeclared for edits: the family's known default still applies.
        assert "response_format" not in edit.params

    @pytest.mark.asyncio
    async def test_a_url_cannot_be_asked_of_an_endpoint_without_it(self):
        generate, edit = _Recorder(), _Recorder()
        port = self._declared_port({"edit": False}, generate, edit)

        with pytest.raises(ValidationError) as exc:
            await port.edit_image(
                image=b"image-bytes",
                prompt="a red dot",
                model="model:openai:dall-e-2",
                response_format="url",
            )

        assert exc.value.details["param"] == "response_format"
        assert edit.params is None
