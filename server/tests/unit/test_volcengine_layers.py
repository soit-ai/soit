"""Layer decomposition on Volcengine Ark: the request SOIT sends and how the answer is read.

LiteLLM has no layer decomposition request, so SOIT writes Ark's own. These
pin what that request carries, how the answer becomes a base image and stacked
layers, and which routes may serve the call at all.
"""

from __future__ import annotations

import base64
import io
from typing import Any

import httpx
import pytest
from PIL import Image

from app.adapters.llm.litellm import LiteLLMPort
from app.adapters.llm.router import LLMRouterPort, RuntimeProviderConfig
from app.adapters.llm.volcengine_layers import (
    ArkRequestError,
    build_request,
    decompose,
    parse_response,
)
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings

CTX = RequestContext(tenant_id="t", workspace_id="w", user_id="u", workspace_role="Dev")
BASE = "https://ark.test/api/v3"


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


_TEXT = {
    "text": "Big Sale",
    "lines": [
        {
            "runs": [
                {
                    "text": "Big ",
                    "style": {
                        "similar_font_family": "Noto Sans SC",
                        "foreground_color": "#FF0000",
                        "bold": True,
                        "italic": False,
                    },
                },
                {"text": "Sale", "style": {"italic": True}},
            ],
            "bounding_box": {"absolute": [12, 24, 108, 56], "normalized": [6, 12, 54, 28]},
        }
    ],
}


def _answer(**overrides: Any) -> dict[str, Any]:
    """An answer in the shape Ark returned on a live call (2026-11-13).

    Recognized text rides on the layer that shows it, boxes come as absolute
    and normalized pairs measured on the base image, and every layer is
    returned at its own scale, not at its box's size.
    """
    payload: dict[str, Any] = {
        "model": "doubao-seedream-5-5-261028",
        "created": 1794547873,
        "data": [
            {
                "b64_json": _b64(_png()),
                "size": "1024x410",
                "output_format": "png",
                "z_index": 2,
                "bounding_box": {"absolute": [10, 20, 110, 60], "normalized": [5, 10, 55, 30]},
                "name": "title",
                "description": "red headline text",
                "text_recognition": _TEXT,
                "background": "transparent",
            },
            {
                "b64_json": _b64(_png()),
                "size": "200x400",
                "output_format": "png",
                "z_index": 0,
                "background": "opaque",
            },
            {
                "b64_json": _b64(_png()),
                "size": "512x1024",
                "output_format": "png",
                "z_index": 1,
                "bounding_box": {"absolute": [30.4, 200, 150, 380.6], "normalized": [152, 500, 750, 952]},
                "name": "cup",
                "background": "transparent",
            },
        ],
        "usage": {"input_images": 1, "generated_images": 3, "output_tokens": 49152, "total_tokens": 49152},
    }
    payload.update(overrides)
    return payload


class _Post:
    def __init__(self, status_code: int = 200, payload: Any = None, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.payload = payload if payload is not None else _answer()
        self.headers = headers or {}
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, url: str, headers: dict[str, str], body: dict[str, Any], timeout: float | None):
        self.calls.append({"url": url, "headers": headers, "body": body, "timeout": timeout})
        return httpx.Response(self.status_code, json=self.payload, headers=self.headers)


class TestRequest:
    def test_carries_the_flag_the_source_and_no_watermark(self) -> None:
        body = build_request(
            model_name="doubao-seedream-5-5-261028",
            image=_png(),
            prompt=None,
            max_layers=None,
            text_recognition=False,
            size=None,
            response_format=None,
        )

        assert body["layer_decomposition"] is True
        assert body["watermark"] is False
        assert body["image"].startswith("data:image/png;base64,")
        assert body["response_format"] == "b64_json"
        # Nothing asked of the options, nothing sent: older models refuse them.
        assert "layer_decomposition_options" not in body
        assert "prompt" not in body and "size" not in body

    def test_counts_the_base_in_max_images(self) -> None:
        body = build_request(
            model_name="m",
            image=_png(),
            prompt="lift the cup and the title",
            max_layers=8,
            text_recognition=True,
            size="2K",
            response_format="url",
        )

        assert body["layer_decomposition_options"] == {"max_images": 9, "text_recognition": True}
        assert body["prompt"] == "lift the cup and the title"
        assert body["size"] == "2K"
        assert body["response_format"] == "url"

    def test_refuses_a_source_ark_cannot_read(self) -> None:
        with pytest.raises(ValidationError):
            build_request(
                model_name="m",
                image=b"GIF89a....",
                prompt=None,
                max_layers=None,
                text_recognition=False,
                size=None,
                response_format=None,
            )


class TestAnswer:
    def test_base_is_z_zero_and_layers_stack_in_order(self) -> None:
        response = parse_response(_answer(), model_name="m", text_recognition=False, request_id="rid")

        assert [layer.z_index for layer in response.layers] == [1, 2]
        assert response.layers[0].bounding_box == (30, 200, 150, 381)
        assert response.layers[1].bounding_box == (10, 20, 110, 60)
        assert response.layers[1].name == "title"
        assert response.layers[1].size == "1024x410"
        assert len(response.images) == 3
        assert response.images[0] is response.base
        assert response.base_size == "200x400"
        assert response.model == "doubao-seedream-5-5-261028"
        assert response.upstream_request_id == "rid"

    def test_recognized_text_stays_on_the_layer_that_shows_it(self) -> None:
        response = parse_response(_answer(), model_name="m", text_recognition=True, request_id=None)

        cup, title = response.layers
        assert cup.text is None and cup.text_lines is None
        assert title.text == "Big Sale"
        assert title.text_lines is not None
        line = title.text_lines[0]
        assert line.text == "Big Sale"
        assert line.bounding_box == (12, 24, 108, 56)
        assert line.runs[0].style.font_family == "Noto Sans SC"
        assert line.runs[0].style.color == "#FF0000"
        assert line.runs[0].style.bold is True
        assert line.runs[0].style.italic is False
        assert line.runs[1].style.italic is True

    def test_text_not_asked_for_is_not_reported(self) -> None:
        response = parse_response(_answer(), model_name="m", text_recognition=False, request_id=None)

        assert all(layer.text is None and layer.text_lines is None for layer in response.layers)

    def test_no_base_is_undeliverable(self) -> None:
        payload = _answer(data=[{"b64_json": _b64(_png()), "z_index": 1}])

        with pytest.raises(KernelError) as refused:
            parse_response(payload, model_name="m", text_recognition=False, request_id=None)

        assert refused.value.code == "IMAGE_UNDELIVERABLE"

    def test_a_layer_without_an_image_is_undeliverable(self) -> None:
        payload = _answer(data=[{"b64_json": _b64(_png()), "z_index": 0}, {"z_index": 1}])

        with pytest.raises(KernelError) as refused:
            parse_response(payload, model_name="m", text_recognition=False, request_id=None)

        assert refused.value.code == "IMAGE_UNDELIVERABLE"


class TestCall:
    @pytest.mark.asyncio
    async def test_posts_to_the_configured_base(self) -> None:
        post = _Post(headers={"x-tt-logid": "log-1"})

        response = await decompose(
            api_base=f"{BASE}/",
            api_key="ark-key",
            model_name="m",
            image=_png(),
            prompt=None,
            max_layers=3,
            text_recognition=False,
            size="1K",
            response_format=None,
            timeout=90.0,
            post=post,
        )

        call = post.calls[0]
        assert call["url"] == f"{BASE}/images/generations"
        assert call["headers"]["Authorization"] == "Bearer ark-key"
        assert call["timeout"] == 90.0
        assert response.upstream_request_id == "log-1"

    @pytest.mark.asyncio
    async def test_needs_the_base_url_the_egress_policy_approved(self) -> None:
        with pytest.raises(ValidationError):
            await decompose(
                api_base=None,
                api_key="k",
                model_name="m",
                image=_png(),
                prompt=None,
                max_layers=None,
                text_recognition=False,
                size=None,
                response_format=None,
                timeout=None,
                post=_Post(),
            )

    @pytest.mark.asyncio
    async def test_a_refusal_keeps_its_status_for_the_retry_policy(self) -> None:
        post = _Post(status_code=429, payload={"error": {"code": "RateLimitExceeded", "message": "slow down"}})

        with pytest.raises(ArkRequestError) as failed:
            await decompose(
                api_base=BASE,
                api_key="k",
                model_name="m",
                image=_png(),
                prompt=None,
                max_layers=None,
                text_recognition=False,
                size=None,
                response_format=None,
                timeout=None,
                post=post,
            )

        assert failed.value.status_code == 429
        assert failed.value.code == "RateLimitExceeded"

    @pytest.mark.asyncio
    async def test_refuses_a_size_tier_ark_does_not_have(self) -> None:
        with pytest.raises(KernelError) as refused:
            await decompose(
                api_base=BASE,
                api_key="k",
                model_name="m",
                image=_png(),
                prompt=None,
                max_layers=None,
                text_recognition=False,
                size="1024x1024",
                response_format=None,
                timeout=None,
                post=_Post(),
            )

        assert refused.value.code == "MODEL_IMAGE_CAPABILITY_UNAVAILABLE"


class TestLiteLLMPort:
    def _port(self, litellm_provider: str | None, post: _Post | None = None) -> LiteLLMPort:
        async def unused(**_kwargs: Any) -> None:
            raise AssertionError("LiteLLM must not be called for a decomposition")

        return LiteLLMPort(
            provider_kind="openai_compatible",
            litellm_provider=litellm_provider,
            api_key="ark-key",
            api_base=BASE,
            completion_fn=unused,
            embedding_fn=unused,
            image_generation_fn=unused,
            image_edit_fn=unused,
            layers_post=post,
        )

    @pytest.mark.asyncio
    async def test_sends_ark_its_own_model_name(self) -> None:
        post = _Post()
        port = self._port("volcengine", post)

        response = await port.decompose_image(
            image=_png(), model="model:ark:doubao-seedream-5-5-261028", response_format="b64_json"
        )

        assert post.calls[0]["body"]["model"] == "doubao-seedream-5-5-261028"
        assert len(response.layers) == 2

    @pytest.mark.asyncio
    async def test_another_provider_has_no_decomposition_route(self) -> None:
        port = self._port("openai")

        with pytest.raises(KernelError) as refused:
            await port.check_image_request("model:main:gpt-image-1", operation="decompose")

        assert refused.value.code == "MODEL_CAPABILITY_UNAVAILABLE"
        assert refused.value.details["reason"] == "no_decomposition_route"

    @pytest.mark.asyncio
    async def test_check_refuses_too_many_layers(self) -> None:
        port = self._port("volcengine")

        with pytest.raises(ValidationError):
            await port.check_image_request("model:ark:m", operation="decompose", max_layers=500)


def _config(slug: str, model_id: str, **overrides: Any) -> RuntimeProviderConfig:
    values: dict[str, Any] = {
        "provider_id": f"prov_{slug}",
        "slug": slug,
        "kind": "openai_compatible",
        "adapter_backend": "litellm",
        "litellm_provider": "volcengine",
        "status": "active",
        "base_url": BASE,
        "credential_secret_id": f"sec_{slug}",
        "provider_model_id": model_id,
        "model_id": model_id,
        "model_status": "active",
        "capability_matrix": {"image_decompose": {"merged": True}},
    }
    values.update(overrides)
    return RuntimeProviderConfig(**values)


class TestRouting:
    @pytest.fixture(autouse=True)
    def _development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "environment", "development")

        async def allow(*_args: Any, **_kwargs: Any) -> None:
            return None

        monkeypatch.setattr(GovernedEgressGuard, "authorize", allow)

    def _router(self, config: RuntimeProviderConfig) -> LLMRouterPort:
        async def resolver(_ctx: Any, provider_key: str, _model_id: str) -> RuntimeProviderConfig | None:
            return config if provider_key == config.slug else None

        return LLMRouterPort(providers={}, provider_resolver=resolver)

    @pytest.mark.asyncio
    async def test_a_volcengine_model_marked_for_decomposition_routes(self) -> None:
        router = self._router(_config("ark", "doubao-seedream-5-5-261028"))

        route = await router.describe_route("model:ark:doubao-seedream-5-5-261028", CTX, ("image_decompose",))

        assert route.target.provider_slug == "ark"

    @pytest.mark.asyncio
    async def test_the_capability_is_opt_in(self) -> None:
        router = self._router(_config("ark", "doubao-seedream-5-5-261028", capability_matrix={}))

        with pytest.raises(KernelError) as refused:
            await router.describe_route("model:ark:doubao-seedream-5-5-261028", CTX, ("image_decompose",))

        assert refused.value.code == "MODEL_CAPABILITY_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_a_provider_without_a_decomposition_request_is_refused(self) -> None:
        router = self._router(_config("main", "gpt-image-1", litellm_provider="openai"))

        with pytest.raises(KernelError) as refused:
            await router.describe_route("model:main:gpt-image-1", CTX, ("image_decompose",))

        assert refused.value.details["reason"] == "no_decomposition_route"
