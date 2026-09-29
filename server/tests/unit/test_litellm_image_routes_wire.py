"""Each image route's entry in litellm_image_routes, checked against the real LiteLLM.

The adapter refuses an image option the routed LiteLLM request cannot carry,
on the strength of the table in ``litellm_image_routes``. These run the real
adapter through the real SDK with every outgoing request captured, one example
model per listed route. An option the table says the route carries must reach
the request: under a name or place LiteLLM maps it to, or, on a route whose
provider takes OpenAI's image request, under OpenAI's own name. One it says
the route does not carry must be refused by the adapter and, forwarded anyway,
must not be mapped onto the request. A made-up option sent beside it tells a
mapped option from one LiteLLM merely copies into the body. A LiteLLM upgrade
that moves an option therefore fails here, in one direction or the other,
before callers see an image that ignored what they asked for.
"""

from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from PIL import Image

import app.adapters.llm.litellm as litellm_adapter
from app.adapters.llm.litellm import LiteLLMPort
from app.adapters.llm.litellm_image_routes import (
    EDIT,
    EDIT_OPTIONS,
    GENERATE,
    GENERATE_OPTIONS,
    OPENAI_EDIT_ROUTES,
    OPENAI_PROTOCOL_ROUTES,
    carried_options,
    image_route,
    is_listed,
    listed_routes,
    takes_openai_sizes,
)
from app.kernel.commons.errors import KernelError, ValidationError

_BASE = "https://provider.test/v1"
_AZURE = "https://provider.test"
_AWS = {"aws_region_name": "us-east-1"}
_VERTEX = {"vertex_project": "project", "vertex_location": "us-central1"}
_API_VERSION = {"api_version": "2025-04-01-preview"}


@dataclass(frozen=True)
class _Example:
    provider_kind: str
    model: str
    litellm_provider: str | None = None
    litellm_params: dict[str, Any] = field(default_factory=dict)
    api_base: str | None = _BASE
    # The sizes a size is tried at, where the usual two are not both taken.
    sizes: tuple[str, ...] = ()


def _custom(provider: str, model: str, **kwargs: Any) -> _Example:
    return _Example("openai_compatible", model, provider, **kwargs)


_EXAMPLES: dict[tuple[str, str], _Example] = {
    (GENERATE, "GPTImageGenerationConfig"): _Example("openai", "gpt-image-1"),
    (GENERATE, "DallE2ImageGenerationConfig"): _Example("openai", "dall-e-2"),
    (GENERATE, "DallE3ImageGenerationConfig"): _Example("openai", "dall-e-3"),
    (GENERATE, "AzureGPTImageGenerationConfig"): _Example(
        "azure_openai", "gpt-image-1", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    (GENERATE, "AzureDallE2ImageGenerationConfig"): _Example(
        "azure_openai", "dall-e-2", litellm_params={"api_version": "2024-02-01"}, api_base=_AZURE
    ),
    (GENERATE, "AzureDallE3ImageGenerationConfig"): _Example(
        "azure_openai", "dall-e-3", litellm_params={"api_version": "2024-02-01"}, api_base=_AZURE
    ),
    (GENERATE, "LiteLLMProxyImageGenerationConfig"): _custom("litellm_proxy", "gpt-image-1"),
    (GENERATE, "AzureFoundryFluxImageGenerationConfig"): _custom(
        "azure_ai", "flux.1-kontext-pro", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    (GENERATE, "AzureFoundryFluxImageGenerationConfig:flux2"): _custom(
        "azure_ai", "flux.2-pro", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    # Deployment names LiteLLM does not know as OpenAI models stay on Azure AI.
    (GENERATE, "AzureFoundryGPTImageGenerationConfig"): _custom(
        "azure_ai", "gpt-image-1-deploy", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    (GENERATE, "AzureFoundryDallE2ImageGenerationConfig"): _custom(
        "azure_ai", "prod-dalle2", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    (GENERATE, "AzureFoundryDallE3ImageGenerationConfig"): _custom(
        "azure_ai", "my-dalle3", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    # MAI's default is 1024x1024 and 1536x1024 is over its pixel limit.
    (GENERATE, "AzureFoundryMAIImageGenerationConfig"): _custom(
        "azure_ai", "mai-image-1", litellm_params=_API_VERSION, api_base=_AZURE, sizes=("1024x768",)
    ),
    (GENERATE, "openai_compatible"): _custom(
        "volcengine", "doubao-seedream-3-0-t2i", api_base="https://provider.test/api/v3"
    ),
    (GENERATE, "XInferenceImageGenerationConfig"): _custom("xinference", "sd3"),
    (GENERATE, "CometAPIImageGenerationConfig"): _custom("cometapi", "dall-e-3"),
    (GENERATE, "ModelScopeImageGenerationConfig"): _custom("modelscope", "Qwen/Qwen-Image"),
    (GENERATE, "RecraftImageGenerationConfig"): _custom("recraft", "recraftv3"),
    (GENERATE, "GoogleImageGenConfig:imagen"): _Example("gemini", "imagen-4.0-generate-001"),
    (GENERATE, "GoogleImageGenConfig:gemini"): _Example("gemini", "gemini-2.5-flash-image"),
    (GENERATE, "VertexAIImagenImageGenerationConfig"): _custom(
        "vertex_ai", "imagen-3.0-generate-002", litellm_params=_VERTEX
    ),
    (GENERATE, "VertexAIGeminiImageGenerationConfig"): _custom(
        "vertex_ai", "gemini-2.5-flash-image", litellm_params=_VERTEX
    ),
    (GENERATE, "DashScopeImageGenerationConfig"): _Example("dashscope", "qwen-image-plus"),
    (GENERATE, "QwenCloudImageGenerationConfig"): _custom("qwencloud", "qwen-image-plus"),
    (GENERATE, "QwenAIPlatformImageGenerationConfig"): _custom("qwen_ai_platform", "qwen-image-plus"),
    (GENERATE, "OpenRouterImageGenerationConfig"): _Example("openrouter", "google/gemini-2.5-flash-image"),
    (GENERATE, "AmazonStabilityConfig"): _Example(
        "bedrock", "stability.stable-diffusion-xl-v1", litellm_params=_AWS, api_base=None
    ),
    (GENERATE, "AmazonStability3Config"): _Example(
        "bedrock", "stability.sd3-large-v1:0", litellm_params=_AWS, api_base=None
    ),
    (GENERATE, "AmazonTitanImageGenerationConfig"): _Example(
        "bedrock", "amazon.titan-image-generator-v2:0", litellm_params=_AWS, api_base=None
    ),
    (GENERATE, "AmazonNovaCanvasConfig"): _Example(
        "bedrock", "amazon.nova-canvas-v1:0", litellm_params=_AWS, api_base=None
    ),
    (GENERATE, "StabilityImageGenerationConfig"): _custom("stability", "sd3-large", api_base=_AZURE),
    (GENERATE, "BlackForestLabsImageGenerationConfig"): _custom(
        "black_forest_labs", "flux-pro-1.1", api_base=None
    ),
    (GENERATE, "BlackForestLabsImageGenerationConfig:ultra"): _custom(
        "black_forest_labs", "flux-pro-1.1-ultra", api_base=None
    ),
    (GENERATE, "FalAIImageGenerationConfig"): _custom("fal_ai", "fal-ai/flux/dev"),
    (GENERATE, "FalAIImagen4Config"): _custom("fal_ai", "fal-ai/imagen4/preview"),
    (GENERATE, "FalAINanoBananaConfig"): _custom("fal_ai", "fal-ai/nano-banana"),
    (GENERATE, "FalAIRecraftV3Config"): _custom("fal_ai", "fal-ai/recraft/v3/text-to-image"),
    (GENERATE, "FalAIBriaConfig"): _custom("fal_ai", "fal-ai/bria/text-to-image/base"),
    (GENERATE, "FalAIFluxProV11Config"): _custom("fal_ai", "fal-ai/flux-pro/v1.1"),
    (GENERATE, "FalAIFluxProV11UltraConfig"): _custom("fal_ai", "fal-ai/flux-pro/v1.1-ultra"),
    (GENERATE, "FalAIFluxSchnellConfig"): _custom("fal_ai", "fal-ai/flux/schnell"),
    (GENERATE, "FalAIBytedanceSeedreamV3Config"): _custom("fal_ai", "fal-ai/bytedance/seedream/v3/text-to-image"),
    (GENERATE, "FalAIBytedanceDreaminaV31Config"): _custom(
        "fal_ai", "fal-ai/bytedance/dreamina/v3.1/text-to-image"
    ),
    (GENERATE, "FalAIIdeogramV3Config"): _custom("fal_ai", "fal-ai/ideogram/v3"),
    (GENERATE, "FalAIStableDiffusionConfig"): _custom("fal_ai", "fal-ai/stable-diffusion-v35-large"),
    (GENERATE, "AimlImageGenerationConfig"): _custom("aiml", "flux-pro"),
    (GENERATE, "RunwayMLImageGenerationConfig"): _custom("runwayml", "gen4_image"),
    (EDIT, "OpenAIImageEditConfig"): _Example("openai", "gpt-image-1"),
    (EDIT, "DallE2ImageEditConfig"): _Example("openai", "dall-e-2"),
    (EDIT, "AzureImageEditConfig"): _Example("azure_openai", "gpt-image-1", litellm_params=_API_VERSION, api_base=_AZURE),
    (EDIT, "LiteLLMProxyImageEditConfig"): _custom("litellm_proxy", "gpt-image-1"),
    (EDIT, "HostedVLLMImageEditConfig"): _custom("hosted_vllm", "Qwen/Qwen-Image-Edit"),
    (EDIT, "AzureFoundryFluxImageEditConfig"): _custom(
        "azure_ai", "flux.1-kontext-pro", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    (EDIT, "AzureFoundryFlux2ImageEditConfig"): _custom(
        "azure_ai", "flux.2-pro", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    (EDIT, "AzureFoundryMAIImageEditConfig"): _custom(
        "azure_ai", "mai-image-1", litellm_params=_API_VERSION, api_base=_AZURE
    ),
    (EDIT, "GeminiImageEditConfig:imagen"): _Example("gemini", "imagen-4.0-generate-001"),
    (EDIT, "GeminiImageEditConfig:gemini"): _Example("gemini", "gemini-2.5-flash-image"),
    (EDIT, "OpenRouterImageEditConfig"): _Example("openrouter", "google/gemini-2.5-flash-image"),
    (EDIT, "RecraftImageEditConfig"): _custom("recraft", "recraftv3"),
    (EDIT, "BedrockAmazonNovaCanvasImageEditConfig"): _Example(
        "bedrock", "amazon.nova-canvas-v1:0", litellm_params=_AWS, api_base=None
    ),
    (EDIT, "BedrockStabilityImageEditConfig"): _Example(
        "bedrock", "stability.stable-image-inpaint-v1:0", litellm_params=_AWS, api_base=None
    ),
    (EDIT, "StabilityImageEditConfig"): _custom("stability", "sd3-large", api_base=_AZURE),
    (EDIT, "BlackForestLabsImageEditConfig"): _custom("black_forest_labs", "flux-kontext-pro", api_base=None),
    (EDIT, "VertexAIImagenImageEditConfig"): _custom("vertex_ai", "imagen-3.0-capability-001", litellm_params=_VERTEX),
    (EDIT, "VertexAIGeminiImageEditConfig"): _custom("vertex_ai", "gemini-2.5-flash-image", litellm_params=_VERTEX),
}


def _png(colour: tuple[int, int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (8, 8), colour).save(buffer, format="PNG")
    return buffer.getvalue()


_IMAGE = _png((10, 20, 30, 255))
_MASK = _png((255, 255, 255, 255))
_CANARY = "zz-canary-sentinel"

# One value per option that nothing else in a request would contain. A size
# is tried at two values, since a route may map one and drop the other.
_SENTINELS: dict[str, Any] = {
    "background": "transparent",
    "output_format": "webp",
    "quality": "high",
    "seed": 424242,
    "strength": 0.37,
    "negative_prompt": "np-sentinel-kq",
    "n": 3,
    "mask": _MASK,
    "response_format": "b64_json",
}
_SIZES = ("1024x1024", "1536x1024")
# The fields OpenAI's image edit request has, which an OpenAI-style edit route
# carries under their own names.
_OPENAI_EDIT_FIELDS = frozenset(GENERATE_OPTIONS) | {"mask"}
_PART = re.compile(
    rb'Content-Disposition: form-data; name="([^"]+)"[^\r\n]*\r\n(?:[^\r\n]+\r\n)*\r\n(.*?)\r\n--', re.S
)


class _Wire:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"created": 1, "data": [{"b64_json": "aGk="}]}, request=request)

    def sent_since(self, index: int) -> httpx.Request | None:
        # The call's own request: a provider that polls sends GETs after it.
        posts = [request for request in self.requests[index:] if request.method != "GET"]
        return posts[0] if posts else None


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> _Wire:
    recorder = _Wire()

    async def send_async(_client: httpx.AsyncClient, request: httpx.Request, *_a: Any, **_k: Any) -> httpx.Response:
        await request.aread()
        return recorder.answer(request)

    def send_sync(_client: httpx.Client, request: httpx.Request, *_a: Any, **_k: Any) -> httpx.Response:
        request.read()
        return recorder.answer(request)

    # LiteLLM's HTTP handler reaches some providers through a sync client even
    # from an async call, so both are captured.
    monkeypatch.setattr(httpx.AsyncClient, "send", send_async)
    monkeypatch.setattr(httpx.Client, "send", send_sync)
    # Black Forest Labs reads its key only from the environment, and Bedrock
    # signs with credentials boto3 would otherwise have to find.
    monkeypatch.setenv("BFL_API_KEY", "bfl-test-key")
    from botocore.credentials import Credentials
    from litellm.llms.bedrock.base_aws_llm import BaseAWSLLM

    monkeypatch.setattr(
        BaseAWSLLM,
        "get_credentials",
        lambda _self, *_a, **_k: Credentials("AKIATESTTESTTEST", "test-secret"),
    )
    # A made-up option the adapter forwards the way it forwards the real ones.
    forward = LiteLLMPort._forward_image_options

    def forward_with_canary(params: dict[str, Any], kwargs: dict[str, Any], names: tuple[str, ...], *, in_extra_body: bool) -> None:
        extra = ("zz_canary",) if "zz_canary" in kwargs else ()
        forward(params, kwargs, (*names, *extra), in_extra_body=in_extra_body)

    monkeypatch.setattr(LiteLLMPort, "_forward_image_options", staticmethod(forward_with_canary))
    return recorder


def _port(example: _Example, *, response_format: bool | None = None) -> LiteLLMPort:
    capabilities = (
        {"response_format_param": {"generate": response_format, "edit": response_format}}
        if response_format is not None
        else {}
    )
    return LiteLLMPort(
        provider_kind=example.provider_kind,
        litellm_provider=example.litellm_provider,
        litellm_params=dict(example.litellm_params),
        api_key="sk-test",
        api_base=example.api_base,
        timeout=30.0,
        image_capabilities=capabilities,
    )


async def _call(port: LiteLLMPort, operation: str, model: str, **kwargs: Any) -> None:
    if operation == GENERATE:
        await port.generate_image(prompt="a red dot", model=f"model:p:{model}", **kwargs)
    else:
        await port.edit_image(image=_IMAGE, prompt="a red dot", model=f"model:p:{model}", **kwargs)


async def _send(wire: _Wire, port: LiteLLMPort, operation: str, model: str, **kwargs: Any) -> httpx.Request | None:
    """The request a call sends; a provider's parser may refuse the canned answer after it."""
    before = len(wire.requests)
    try:
        await _call(port, operation, model, **kwargs)
    except KernelError:
        raise
    except Exception:  # noqa: BLE001 - see the docstring
        pass
    return wire.sent_since(before)


def _leaves(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        return [leaf for key, item in value.items() for leaf in _leaves(item, (*path, str(key)))]
    if isinstance(value, list):
        return [leaf for index, item in enumerate(value) for leaf in _leaves(item, (*path, str(index)))]
    return [(path, value)]


def _fields(request: httpx.Request) -> dict[tuple[str, ...], Any]:
    body = request.content
    if "multipart" in request.headers.get("content-type", ""):
        return {(name.decode(),): value for name, value in _PART.findall(body)}
    try:
        return dict(_leaves(json.loads(body)))
    except ValueError:
        return {("<raw>",): body}


def _matches(value: Any, option: str, sentinel: Any, masks: list[bytes]) -> bool:
    if option == "mask":
        if isinstance(value, bytes):
            return any(mask in value for mask in masks)
        return isinstance(value, str) and any(base64.b64encode(mask).decode() in value for mask in masks)
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    if isinstance(sentinel, str):
        return isinstance(value, str) and sentinel in value
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int | float):
        return value == sentinel
    try:
        return float(value) == float(sentinel)
    except (TypeError, ValueError):
        return False


def _where(request: httpx.Request, option: str, sentinel: Any, masks: list[bytes]) -> set[tuple[str, ...]]:
    """Where a value sits in the request, outside a literal extra_body no provider reads."""
    return {
        path
        for path, value in _fields(request).items()
        if "extra_body" not in path and _matches(value, option, sentinel, masks)
    }


async def _verdict(wire: _Wire, operation: str, route: str, option: str) -> str:
    """'mapped', 'copied' (only where any unknown key lands), 'absent' or 'refused'."""
    example = _EXAMPLES[(operation, route)]
    # Every request here is asked for response_format or not alike, so that
    # only the option under test tells them apart.
    port = _port(example, response_format=option == "response_format")
    model_name = port._model_name(f"model:p:{example.model}")
    masks = [_MASK, port._mask_for_provider(_MASK, model_name)]

    baseline = await _send(wire, _port(example, response_format=False), operation, example.model)
    canary = await _send(wire, _port(example, response_format=False), operation, example.model, zz_canary=_CANARY)
    copied_under = {path[:-1] for path in (_where(canary, "canary", _CANARY, masks) if canary else set())}

    sizes = example.sizes or _SIZES
    tries = [{"size": size} for size in sizes] if option == "size" else [{option: _SENTINELS.get(option)}]
    if option == "response_format":
        tries = [{}]
    verdicts = []
    for kwargs in tries:
        request = await _send(wire, port, operation, example.model, **kwargs)
        if request is None:
            verdicts.append("refused")
            continue
        if option == "size":
            changed = baseline is None or _fields(request) != _fields(baseline)
            where = _where(request, "size", kwargs["size"], masks)
            if not changed:
                verdicts.append("absent")
            elif where and all(path[:-1] in copied_under and path[-1] == "size" for path in where):
                verdicts.append("copied")
            else:
                verdicts.append("mapped")
            continue
        sentinel = _SENTINELS[option]
        where = _where(request, option, sentinel, masks)
        if baseline is not None:
            where -= _where(baseline, option, sentinel, masks)
        if not where:
            verdicts.append("absent")
        elif all(path[:-1] in copied_under and path[-1] == option for path in where):
            verdicts.append("copied")
        else:
            verdicts.append("mapped")
    for best in ("mapped", "copied", "absent"):
        if best in verdicts:
            return best
    return "refused"


def _options(operation: str) -> tuple[str, ...]:
    return EDIT_OPTIONS if operation == EDIT else GENERATE_OPTIONS


def _reaches(route: str, operation: str, option: str, verdict: str) -> bool:
    """What counts as carried: mapped, or under OpenAI's name to an OpenAI-style API."""
    if operation == GENERATE and route in OPENAI_PROTOCOL_ROUTES:
        return verdict in ("mapped", "copied")
    if operation == EDIT and route in OPENAI_EDIT_ROUTES and option in _OPENAI_EDIT_FIELDS:
        return verdict in ("mapped", "copied")
    return verdict == "mapped"


_CELLS = [
    (operation, route, option, option in carried_options(route, operation))
    for operation, route in listed_routes()
    for option in _options(operation)
]
_CARRIED = [pytest.param(o, r, x, id=f"{o}-{r}-{x}") for o, r, x, carried in _CELLS if carried]
_NOT_CARRIED = [pytest.param(o, r, x, id=f"{o}-{r}-{x}") for o, r, x, carried in _CELLS if not carried]
_REFUSABLE = [param for param in _NOT_CARRIED if param.values[2] != "response_format"]


@pytest.mark.parametrize(("operation", "route"), listed_routes())
def test_every_listed_route_has_an_example_that_takes_it(operation: str, route: str) -> None:
    example = _EXAMPLES[(operation, route)]
    model_name = _port(example)._model_name(f"model:p:{example.model}")

    assert image_route(model_name, operation) == route


@pytest.mark.asyncio
@pytest.mark.parametrize(("operation", "route", "option"), _CARRIED)
async def test_an_option_the_route_carries_reaches_the_provider(wire: _Wire, operation: str, route: str, option: str) -> None:
    assert _reaches(route, operation, option, await _verdict(wire, operation, route, option))


@pytest.mark.asyncio
@pytest.mark.parametrize(("operation", "route", "option"), _REFUSABLE)
async def test_an_option_the_route_cannot_carry_is_refused_before_the_wire(
    wire: _Wire, operation: str, route: str, option: str
) -> None:
    example = _EXAMPLES[(operation, route)]
    kwargs = {"size": _SIZES[0]} if option == "size" else {option: _SENTINELS[option]}

    with pytest.raises(KernelError) as refused:
        await _call(_port(example), operation, example.model, **kwargs)

    assert wire.requests == []
    assert refused.value.code == "MODEL_IMAGE_CAPABILITY_UNAVAILABLE"
    assert refused.value.details["reason"] == "route_cannot_carry"
    assert refused.value.details["param"] == option
    assert refused.value.details["route"] == route


@pytest.mark.asyncio
@pytest.mark.parametrize(("operation", "route", "option"), _NOT_CARRIED)
async def test_an_option_the_route_cannot_carry_would_not_have_reached_the_provider(
    wire: _Wire, monkeypatch: pytest.MonkeyPatch, operation: str, route: str, option: str
) -> None:
    # Forwarded regardless, LiteLLM drops it, refuses it, or only copies it
    # where the provider's API has no such field: the table is not stricter
    # than the library. Only the option under test is let through, so the
    # call fails, if it fails, on that option and not on another one.
    real = carried_options
    monkeypatch.setattr(
        litellm_adapter, "carried_options", lambda r, o: real(r, o) | {option}
    )

    assert not _reaches(route, operation, option, await _verdict(wire, operation, route, option))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "route"),
    [(o, r) for o, r in listed_routes() if "response_format" not in carried_options(r, o)],
)
async def test_a_route_without_response_format_is_not_sent_one(wire: _Wire, operation: str, route: str) -> None:
    # LiteLLM refuses the parameter outright on many of these, so a model that
    # declared nothing would fail on every call; a URL cannot be promised.
    example = _EXAMPLES[(operation, route)]

    request = await _send(wire, _port(example), operation, example.model)
    with pytest.raises(ValidationError):
        await _call(_port(example), operation, example.model, response_format="url")

    assert request is not None, "the call reached the wire"
    assert not _where(request, "response_format", "b64_json", [])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "route"),
    [(o, r) for o, r in listed_routes() if "output_format" not in carried_options(r, o)],
)
async def test_png_is_taken_unsent_where_the_route_carries_no_format(
    wire: _Wire, operation: str, route: str
) -> None:
    # The provider answers in its own format and the artifact is typed from
    # the returned bytes; a png the route has no place for is not sent.
    example = _EXAMPLES[(operation, route)]

    baseline = await _send(wire, _port(example), operation, example.model)
    request = await _send(wire, _port(example), operation, example.model, output_format="png")

    assert request is not None, "the call reached the wire"
    assert baseline is not None
    assert _fields(request).keys() == _fields(baseline).keys()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "route"),
    [(o, r) for o, r in listed_routes() if not takes_openai_sizes(r, o)],
)
async def test_an_auto_size_is_taken_unsent_where_the_route_reads_no_openai_size(
    wire: _Wire, operation: str, route: str
) -> None:
    # auto leaves the size to the provider, as leaving it out does; a route
    # that turns a size into dimensions of its own has no auto to send.
    example = _EXAMPLES[(operation, route)]

    baseline = await _send(wire, _port(example), operation, example.model)
    request = await _send(wire, _port(example), operation, example.model, size="auto")

    assert request is not None, "the call reached the wire"
    assert baseline is not None
    assert _fields(request).keys() == _fields(baseline).keys()


# Model names that walk every branch of LiteLLM's image config selectors for the
# providers SOIT can route to.
_SELECTOR_MODELS: dict[str, list[str]] = {
    "openai": ["gpt-image-1", "gpt-image-1-mini", "chatgpt-image-latest", "dall-e-2", "dall-e-3", "doubao-seedream-3-0"],
    "azure": ["gpt-image-1", "dall-e-2", "dall-e-3", "mai-image-1", "my-deployment"],
    "azure_ai": [
        "gpt-image-1",
        "gpt-image-1-deploy",
        "dall-e-2",
        "dall-e-3",
        "prod-dalle2",
        "my-dalle3",
        "images-prod",
        "flux.1-kontext-pro",
        "flux.2-pro",
        "FLUX-1.1-pro",
        "mai-image-1",
    ],
    "litellm_proxy": ["gpt-image-1", "any-model"],
    "gemini": ["imagen-4.0-generate-001", "gemini-2.5-flash-image"],
    "vertex_ai": ["imagen-3.0-generate-002", "imagen-3.0-capability-001", "gemini-2.5-flash-image"],
    "openrouter": ["google/gemini-2.5-flash-image"],
    "bedrock": [
        "stability.stable-diffusion-xl-v1",
        "stability.sd3-large-v1:0",
        "stability.stable-image-core-v1:1",
        "stability.stable-image-inpaint-v1:0",
        "amazon.titan-image-generator-v2:0",
        "amazon.nova-canvas-v1:0",
        "us.amazon.nova-canvas-v1:0",
    ],
    "stability": ["sd3-large", "stable-image-ultra"],
    "black_forest_labs": ["flux-pro-1.1", "flux-pro-1.1-ultra", "flux-kontext-pro", "flux-pro-1.0-fill"],
    "dashscope": ["qwen-image-plus", "wanx-v1"],
    "qwencloud": ["qwen-image-plus"],
    "qwen_ai_platform": ["qwen-image-plus"],
    "recraft": ["recraftv3"],
    "xinference": ["sd3"],
    "fal_ai": [
        "fal-ai/flux/dev",
        "fal-ai/imagen4/preview",
        "fal-ai/nano-banana",
        "fal-ai/recraft/v3/text-to-image",
        "fal-ai/bria/text-to-image/base",
        "fal-ai/flux-pro/v1.1",
        "fal-ai/flux-pro/v1.1-ultra",
        "fal-ai/flux/schnell",
        "fal-ai/bytedance/seedream/v3/text-to-image",
        "fal-ai/bytedance/dreamina/v3.1/text-to-image",
        "fal-ai/ideogram/v3",
        "fal-ai/stable-diffusion-v35-large",
    ],
    "aiml": ["flux-pro"],
    "cometapi": ["dall-e-3"],
    "modelscope": ["Qwen/Qwen-Image"],
    "runwayml": ["gen4_image"],
    "volcengine": ["doubao-seedream-3-0-t2i"],
    "hosted_vllm": ["sdxl"],
    "together_ai": ["black-forest-labs/FLUX.1-schnell"],
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "route"),
    [(GENERATE, "GPTImageGenerationConfig"), (EDIT, "OpenAIImageEditConfig")],
)
async def test_an_auto_size_is_sent_where_the_route_reads_openai_sizes(
    wire: _Wire, operation: str, route: str
) -> None:
    example = _EXAMPLES[(operation, route)]

    request = await _send(wire, _port(example), operation, example.model, size="auto")

    assert request is not None
    assert _where(request, "size", "auto", [])


def test_a_provider_litellm_finds_by_signing_in_is_placed_without_the_network(
    wire: _Wire, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # LiteLLM places chatgpt and github_copilot models by starting a device
    # login; naming the route must not.
    monkeypatch.setenv("CHATGPT_TOKEN_DIR", str(tmp_path))
    monkeypatch.setenv("GITHUB_COPILOT_TOKEN_DIR", str(tmp_path))

    for prefix in ("chatgpt", "github_copilot"):
        assert image_route(f"{prefix}/gpt-image-1", GENERATE) == "openai_compatible"
        assert image_route(f"{prefix}/gpt-image-1", EDIT) is None

    assert wire.requests == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("operation", [GENERATE, EDIT])
@pytest.mark.parametrize("prefix", sorted(_SELECTOR_MODELS))
def test_every_route_litellm_picks_is_in_the_table(prefix: str, operation: str) -> None:
    # A route missing from the table would refuse every option, including
    # ones LiteLLM delivers, so a new branch in LiteLLM fails here first.
    unlisted = [
        (model, route)
        for model in _SELECTOR_MODELS[prefix]
        if (route := image_route(f"{prefix}/{model}", operation)) is not None
        and not is_listed(route, operation)
    ]

    assert unlisted == []
