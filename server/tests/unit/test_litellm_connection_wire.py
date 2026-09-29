"""Where a provider's connection settings go on the wire.

An operator's litellm_params carry connection settings and credentials: extra
headers, OpenAI's organization and project, an Azure AD token, cloud keys.
LiteLLM treats a keyword it does not know as a field of the provider request,
so these run the real SDK with every outgoing request captured and check that
each setting reaches the provider as a header, or not at all, and never in the
request body. Vertex AI's project and location and Bedrock's keys and region
must still reach the URL and the signature they are read for.
"""

import contextlib
import io
import json
from typing import Any

import httpx
import pytest
from PIL import Image

from app.adapters.llm.litellm import LiteLLMPort, _azure_ad_token_provider
from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.runtime_config import (
    LITELLM_SECRET_BINDING_ALLOWLIST,
    LITELLM_STATIC_PARAM_ALLOWLIST,
)

_API_KEY = "sk-sentinel-api-key"
_AD_TOKEN = "sentinel-azure-ad-token"

# The operator settings a provider can carry besides its API key, which the
# router hands the adapter as api_key.
_SETTINGS = sorted((LITELLM_STATIC_PARAM_ALLOWLIST | LITELLM_SECRET_BINDING_ALLOWLIST) - {"api_key"})

_ROUTES = [
    pytest.param("openai", None, "https://api.provider.test/v1", id="openai"),
    pytest.param("azure_openai", None, "https://resource.provider.test", id="azure"),
    pytest.param("openai_compatible", "litellm_proxy", "https://gateway.provider.test/v1", id="openai-compatible"),
]
_OPENAI_ROUTES = [route for route in _ROUTES if route.id != "azure"]
_OPERATIONS = ["generate", "edit", "embed"]

# The settings Vertex AI and Bedrock read, at values their URLs and
# signatures take and nothing else in a request contains.
_VERTEX = {"vertex_project": "sentinel-vertex-project", "vertex_location": "europe-west4"}
_AWS = {
    "aws_region_name": "eu-west-3",
    "aws_access_key_id": "AKIASENTINELKEYID",
    "aws_secret_access_key": "sentinel-aws-secret-access-key",
    "aws_session_token": "sentinel-aws-session-token",
}
_VERTEX_TOKEN = "ya29.sentinel-vertex-token"
_VERTEX_ROUTES = [
    pytest.param("generate", "imagen-3.0-generate-002", id="imagen-generate"),
    pytest.param("generate", "gemini-2.5-flash-image", id="gemini-generate"),
    pytest.param("edit", "imagen-3.0-capability-001", id="imagen-edit"),
    pytest.param("edit", "gemini-2.5-flash-image", id="gemini-edit"),
    pytest.param("embed", "text-embedding-004", id="embed"),
]
_BEDROCK_ROUTES = [
    pytest.param("generate", "stability.stable-diffusion-xl-v1", id="stability-generate"),
    pytest.param("generate", "stability.sd3-large-v1:0", id="stability3-generate"),
    pytest.param("generate", "amazon.titan-image-generator-v2:0", id="titan-generate"),
    pytest.param("generate", "amazon.nova-canvas-v1:0", id="nova-canvas-generate"),
    pytest.param("edit", "amazon.nova-canvas-v1:0", id="nova-canvas-edit"),
    pytest.param("edit", "stability.stable-image-inpaint-v1:0", id="stability-edit"),
    pytest.param("embed", "amazon.titan-embed-text-v2:0", id="embed"),
]
_CLOUD_ROUTES = [
    pytest.param("vertex_ai", *route.values, id=f"vertex-{route.id}") for route in _VERTEX_ROUTES
] + [pytest.param("bedrock", *route.values, id=f"bedrock-{route.id}") for route in _BEDROCK_ROUTES]


def _setting(name: str) -> Any:
    if name == "extra_headers":
        return {"X-Gateway-Key": "sentinel-extra-header"}
    if name == "drop_params":
        return True
    return f"sentinel-{name.replace('_', '-')}"


def _sentinels(settings: dict[str, Any]) -> list[str]:
    values = [_API_KEY]
    for value in settings.values():
        if isinstance(value, dict):
            values.extend(str(item) for item in value.values())
        elif isinstance(value, str):
            values.append(value)
    return values


class _Wire:
    """Every request LiteLLM sends, answered with one image or one embedding."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/embeddings"):
            answer: dict[str, Any] = {
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                "model": "text-embedding-3-small",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            }
        else:
            answer = {"created": 1, "data": [{"b64_json": "aGk="}]}
        return httpx.Response(200, json=answer, request=request)

    @property
    def last(self) -> httpx.Request:
        assert self.requests, "the call reached the wire"
        return self.requests[-1]

    def field_names(self) -> set[str]:
        """The body's field names, at every depth of a JSON body."""
        request = self.last
        if "json" in request.headers.get("content-type", ""):
            return _keys(json.loads(request.content))
        return {
            part.split(b'"', 1)[0].decode()
            for part in request.content.split(b'name="')[1:]
        }


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {name for item in value.values() for name in _keys(item)}
    if isinstance(value, list):
        return {name for item in value for name in _keys(item)}
    return set()


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> _Wire:
    # LiteLLM builds its own clients, and ignores an injected one on some
    # routes, so the capture sits under all of them.
    recorder = _Wire()

    async def send_async(_client: httpx.AsyncClient, request: httpx.Request, *_args: Any, **_kwargs: Any) -> httpx.Response:
        await request.aread()
        return recorder.answer(request)

    def send_sync(_client: httpx.Client, request: httpx.Request, *_args: Any, **_kwargs: Any) -> httpx.Response:
        request.read()
        return recorder.answer(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send_async)
    monkeypatch.setattr(httpx.Client, "send", send_sync)
    return recorder


@pytest.fixture
def cloud_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vertex AI and Bedrock credentials found without the network.

    Vertex AI is handed a token for the project it names, where it would ask
    Google's default credentials. Bedrock signs with the keys it is given,
    which boto3 could otherwise go looking for.
    """
    from botocore.credentials import Credentials
    from litellm.llms.bedrock.base_aws_llm import BaseAWSLLM
    from litellm.llms.vertex_ai.vertex_llm_base import VertexBase

    def token(_self: Any, *_args: Any, project_id: str | None = None, **_kwargs: Any) -> tuple[str, Any]:
        return _VERTEX_TOKEN, project_id

    async def token_async(_self: Any, *_args: Any, project_id: str | None = None, **_kwargs: Any) -> tuple[str, Any]:
        return _VERTEX_TOKEN, project_id

    def keys(
        _self: Any,
        *_args: Any,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        **_kwargs: Any,
    ) -> Credentials:
        return Credentials(aws_access_key_id, aws_secret_access_key, aws_session_token)

    monkeypatch.setattr(VertexBase, "_ensure_access_token", token)
    monkeypatch.setattr(VertexBase, "_ensure_access_token_async", token_async)
    monkeypatch.setattr(BaseAWSLLM, "get_credentials", keys)


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _call(
    operation: str,
    *,
    provider_kind: str,
    litellm_provider: str | None,
    api_base: str | None,
    settings: dict[str, Any],
    api_key: str | None = _API_KEY,
    model: str | None = None,
) -> None:
    port = LiteLLMPort(
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
        api_key=api_key,
        api_base=api_base,
        litellm_params=settings,
    )
    if operation == "generate":
        await port.generate_image(prompt="a red dot", model=f"model:p:{model or 'gpt-image-1'}")
    elif operation == "edit":
        await port.edit_image(image=_png(), prompt="a red dot", model=f"model:p:{model or 'gpt-image-1'}")
    else:
        await port.embed(["a red dot"], model=f"model:p:{model or 'text-embedding-3-small'}")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize(("provider_kind", "litellm_provider", "api_base"), _ROUTES)
@pytest.mark.parametrize("name", _SETTINGS)
async def test_no_connection_setting_reaches_a_request_body(
    wire, operation, provider_kind, litellm_provider, api_base, name
):
    settings = {name: _setting(name)}
    await _call(
        operation,
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
        api_base=api_base,
        settings=settings,
    )

    body = wire.last.content
    for value in _sentinels(settings):
        assert value.encode() not in body
    assert name not in wire.field_names()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize(("provider_kind", "litellm_provider", "api_base"), _ROUTES)
async def test_a_provider_carrying_every_setting_sends_none_in_the_body(
    wire, operation, provider_kind, litellm_provider, api_base
):
    settings = {name: _setting(name) for name in _SETTINGS}
    await _call(
        operation,
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
        api_base=api_base,
        settings=settings,
    )

    body = wire.last.content
    for value in _sentinels(settings):
        assert value.encode() not in body
    assert not wire.field_names() & set(_SETTINGS)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", _OPERATIONS)
async def test_an_azure_ad_token_authorizes_an_azure_request(wire, operation):
    await _call(
        operation,
        provider_kind="azure_openai",
        litellm_provider=None,
        api_base="https://resource.provider.test",
        settings={"azure_ad_token": _AD_TOKEN},
        api_key=None,
    )

    request = wire.last
    assert request.headers["authorization"] == f"Bearer {_AD_TOKEN}"
    assert "api-key" not in request.headers
    assert _AD_TOKEN.encode() not in request.content


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize(("provider_kind", "litellm_provider", "api_base"), _ROUTES)
async def test_an_api_key_authorizes_a_request(wire, operation, provider_kind, litellm_provider, api_base):
    await _call(
        operation,
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
        api_base=api_base,
        settings={},
    )

    headers = wire.last.headers
    if provider_kind == "azure_openai":
        assert headers["api-key"] == _API_KEY
    else:
        assert headers["authorization"] == f"Bearer {_API_KEY}"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize(("provider_kind", "litellm_provider", "api_base"), _ROUTES)
async def test_extra_headers_are_sent_as_request_headers(wire, operation, provider_kind, litellm_provider, api_base):
    await _call(
        operation,
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
        api_base=api_base,
        settings={"extra_headers": {"X-Gateway-Key": "sentinel-extra-header"}},
    )

    assert wire.last.headers["x-gateway-key"] == "sentinel-extra-header"


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize(("provider_kind", "litellm_provider", "api_base"), _OPENAI_ROUTES)
async def test_organization_and_project_are_sent_as_openai_headers(
    wire, operation, provider_kind, litellm_provider, api_base
):
    await _call(
        operation,
        provider_kind=provider_kind,
        litellm_provider=litellm_provider,
        api_base=api_base,
        settings={"organization": "org-sentinel", "project": "proj-sentinel"},
    )

    headers = wire.last.headers
    assert headers["openai-organization"] == "org-sentinel"
    assert headers["openai-project"] == "proj-sentinel"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("litellm_provider", "model"),
    [("gemini", "imagen-4.0-generate-001"), ("stability", "sd3-large")],
)
async def test_a_generation_through_litellm_generic_image_handler_keeps_its_headers(wire, litellm_provider, model):
    # That handler reads headers only from the extra_headers keyword, which
    # these providers keep out of the body.
    with contextlib.suppress(Exception):
        # The mock answers in OpenAI's shape, which these parsers may refuse
        # after the request has been captured.
        await _call(
            "generate",
            provider_kind="openai_compatible",
            litellm_provider=litellm_provider,
            api_base="https://images.provider.test",
            settings={"extra_headers": {"X-Gateway-Key": "sentinel-extra-header"}, "drop_params": True},
            model=model,
        )

    request = wire.last
    assert request.headers["x-gateway-key"] == "sentinel-extra-header"
    assert b"sentinel-extra-header" not in request.content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("litellm_provider", "model"),
    [
        ("openrouter", "google/gemini-2.5-flash-image"),
        ("dashscope", "wan2.2-t2i-flash"),
        ("vertex_ai", "imagegeneration@006"),
    ],
)
async def test_a_generation_that_would_copy_headers_into_its_body_is_sent_none(wire, litellm_provider, model):
    settings = {
        "extra_headers": {"X-Gateway-Key": "sentinel-extra-header"},
        "project": "sentinel-project",
        "azure_ad_token": _AD_TOKEN,
        "drop_params": True,
    }
    with contextlib.suppress(Exception):
        await _call(
            "generate",
            provider_kind="openai_compatible",
            litellm_provider=litellm_provider,
            api_base="https://images.provider.test",
            settings=settings,
            model=model,
        )

    body = wire.last.content
    for value in _sentinels(settings):
        assert value.encode() not in body


async def _call_cloud(provider: str, operation: str, model: str, *, settings: dict[str, Any], api_base: str | None) -> None:
    # Vertex AI signs in with Google's credentials and Bedrock with AWS keys,
    # so neither is given an API key, which Bedrock would take as a bearer
    # token in place of its keys.
    with contextlib.suppress(Exception):
        # These parsers may refuse the mock's answer once the request has
        # been captured.
        await _call(
            operation,
            provider_kind="openai_compatible",
            litellm_provider=provider,
            api_base=api_base,
            settings=settings,
            api_key=None,
            model=model,
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures("cloud_credentials")
@pytest.mark.parametrize(("operation", "model"), _VERTEX_ROUTES)
async def test_vertex_ai_builds_its_url_from_its_project_and_location_and_sends_neither(wire, operation, model):
    # Imagen's generation copied both into its parameters, beside sampleCount.
    await _call_cloud("vertex_ai", operation, model, settings=dict(_VERTEX), api_base=None)

    request = wire.last
    assert request.url.host == "europe-west4-aiplatform.googleapis.com"
    assert "/projects/sentinel-vertex-project/locations/europe-west4/" in request.url.path
    assert request.headers["authorization"] == f"Bearer {_VERTEX_TOKEN}"
    for value in _VERTEX.values():
        assert value.encode() not in request.content
    assert not wire.field_names() & set(_VERTEX)


@pytest.mark.asyncio
@pytest.mark.usefixtures("cloud_credentials")
@pytest.mark.parametrize(("operation", "model"), _BEDROCK_ROUTES)
async def test_bedrock_signs_with_its_keys_in_its_region_and_sends_none_in_the_body(wire, operation, model):
    await _call_cloud("bedrock", operation, model, settings=dict(_AWS), api_base=None)

    request = wire.last
    assert request.url.host == "bedrock-runtime.eu-west-3.amazonaws.com"
    assert "Credential=AKIASENTINELKEYID/" in request.headers["authorization"]
    assert "/eu-west-3/bedrock/aws4_request" in request.headers["authorization"]
    assert request.headers["x-amz-security-token"] == "sentinel-aws-session-token"
    for value in _AWS.values():
        assert value.encode() not in request.content
    assert not wire.field_names() & set(_AWS)


@pytest.mark.asyncio
@pytest.mark.usefixtures("cloud_credentials")
@pytest.mark.parametrize("api_base", [None, "https://gateway.provider.test/v1"], ids=["direct", "api-base"])
@pytest.mark.parametrize(("provider", "operation", "model"), _CLOUD_ROUTES)
async def test_a_cloud_provider_carrying_every_setting_sends_none_in_the_body(
    wire, provider, operation, model, api_base
):
    own = _VERTEX if provider == "vertex_ai" else _AWS
    settings = {**{name: _setting(name) for name in _SETTINGS}, **own}
    await _call_cloud(provider, operation, model, settings=settings, api_base=api_base)

    body = wire.last.content
    for value in _sentinels(settings):
        assert value.encode() not in body
    assert not wire.field_names() & set(_SETTINGS)


def test_one_azure_ad_token_keeps_one_provider():
    # LiteLLM keys its cached Azure clients on the provider's identity.
    provider = _azure_ad_token_provider(_AD_TOKEN)

    assert provider() == _AD_TOKEN
    assert _azure_ad_token_provider(_AD_TOKEN) is provider
    assert _azure_ad_token_provider("another-token") is not provider


@pytest.mark.asyncio
async def test_extra_headers_that_are_not_an_object_are_refused(wire):
    with pytest.raises(ValidationError, match="extra_headers must be an object"):
        await _call(
            "generate",
            provider_kind="openai",
            litellm_provider=None,
            api_base="https://api.provider.test/v1",
            settings={"extra_headers": "X-Gateway-Key: sentinel"},
        )

    assert not wire.requests
