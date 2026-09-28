"""Where a provider's connection settings go on the wire.

An operator's litellm_params carry connection settings and credentials: extra
headers, OpenAI's organization and project, an Azure AD token, cloud keys.
LiteLLM treats a keyword it does not know as a field of the provider request,
so these run the real SDK with every outgoing request captured and check that
each setting reaches the provider as a header, or not at all, and never in the
request body.
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
        request = self.last
        if "json" in request.headers.get("content-type", ""):
            return set(json.loads(request.content))
        return {
            part.split(b'"', 1)[0].decode()
            for part in request.content.split(b'name="')[1:]
        }


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


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _call(
    operation: str,
    *,
    provider_kind: str,
    litellm_provider: str | None,
    api_base: str,
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
