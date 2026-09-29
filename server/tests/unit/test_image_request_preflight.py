"""An image request its route cannot serve as asked is refused before a run opens.

The images endpoints ask the gateway first. It picks the target the call would
pick, from provider configuration alone, and applies the checks the call makes
before the provider: the credential's model list, the model's declared traits,
and what its LiteLLM route can carry. Nothing is admitted, recorded or billed,
no secret is resolved and nothing reaches the network.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llm.router import LLMRouterPort, RuntimeProviderConfig
from app.kernel.commons.errors import ForbiddenError, KernelError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.policy import LLMPolicyGateway
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings

CTX = RequestContext(tenant_id="t", workspace_id="w", user_id="u", workspace_role="Dev")


@pytest.fixture(autouse=True)
def _development(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setattr(settings, "environment", "development")
    authorized: list[str] = []

    async def record_egress(*_args: Any, **_kwargs: Any) -> None:
        authorized.append("egress")

    monkeypatch.setattr(GovernedEgressGuard, "authorize", record_egress)
    return authorized


def _config(slug: str, model_id: str, **overrides: Any) -> RuntimeProviderConfig:
    values: dict[str, Any] = {
        "provider_id": f"prov_{slug}",
        "slug": slug,
        "kind": "openai",
        "adapter_backend": "litellm",
        "status": "active",
        "base_url": "https://provider.test/v1",
        "credential_secret_id": f"sec_{slug}",
        "provider_model_id": model_id,
        "model_id": model_id,
        "model_status": "active",
        "capability_matrix": {
            "image_generation": {"merged": True},
            "image_edit": {"merged": True},
        },
    }
    values.update(overrides)
    return RuntimeProviderConfig(**values)


class _Secrets:
    def __init__(self) -> None:
        self.resolved: list[str] = []

    async def get_secret(self, *, secret_id: str) -> str:
        self.resolved.append(secret_id)
        return "sk-resolved"


def _router(configs: dict[str, RuntimeProviderConfig], secrets: _Secrets | None = None) -> LLMRouterPort:
    return LLMRouterPort(
        providers={},
        provider_resolver=lambda _ctx, slug, _model_id: configs.get(slug),
        secrets_resolver=lambda _ctx: secrets or _Secrets(),
    )


def _gateway(router: LLMRouterPort, ctx: RequestContext = CTX, **kwargs: Any) -> LLMPolicyGateway:
    return LLMPolicyGateway(router, ctx, max_retries=0, **kwargs)


class TestDescribedRoute:
    @pytest.mark.asyncio
    async def test_it_resolves_no_secret_and_reaches_no_network(self, _development: list[str]) -> None:
        secrets = _Secrets()
        router = _router({"openai-main": _config("openai-main", "gpt-image-1")}, secrets)

        route = await router.describe_route("model:openai-main:gpt-image-1", CTX, ("image_edit",))

        assert secrets.resolved == []
        assert _development == []
        assert route.port.api_key is None

    @pytest.mark.asyncio
    async def test_the_call_still_resolves_in_full(self, _development: list[str]) -> None:
        secrets = _Secrets()
        router = _router({"openai-main": _config("openai-main", "gpt-image-1")}, secrets)

        route = await router.resolve_route("model:openai-main:gpt-image-1", CTX, ("image_edit",))

        assert secrets.resolved == ["sec_openai-main"]
        assert _development == ["egress"]
        assert route.port.api_key == "sk-resolved"


class TestRoutesThatCannotServeImages:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("connect", [True, False])
    async def test_a_provider_litellm_cannot_edit_with_has_no_image_edit(self, connect: bool) -> None:
        router = _router(
            {"ark": _config("ark", "doubao-seedream", kind="openai_compatible", litellm_provider="volcengine")}
        )
        resolve = router.resolve_route if connect else router.describe_route

        with pytest.raises(KernelError) as refused:
            await resolve("model:ark:doubao-seedream", CTX, ("image_edit",))

        assert refused.value.code == "MODEL_CAPABILITY_UNAVAILABLE"
        assert refused.value.details["capability"] == "image_edit"
        assert refused.value.details["reason"] == "no_litellm_route"

    @pytest.mark.asyncio
    async def test_the_egress_check_comes_before_the_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A provider egress policy denies is refused as such, before LiteLLM is
        # asked anything about it.
        from app.kernel.commons.errors import ForbiddenError as Denied

        async def deny(*_args: Any, **_kwargs: Any) -> None:
            raise Denied("egress denied")

        monkeypatch.setattr(GovernedEgressGuard, "authorize", deny)
        router = _router(
            {"ark": _config("ark", "doubao-seedream", kind="openai_compatible", litellm_provider="volcengine")}
        )

        with pytest.raises(Denied):
            await router.resolve_route("model:ark:doubao-seedream", CTX, ("image_edit",))

    @pytest.mark.asyncio
    async def test_a_native_adapter_serves_no_image(self) -> None:
        router = _router({"openai-main": _config("openai-main", "gpt-image-1", adapter_backend="native")})

        with pytest.raises(KernelError) as refused:
            await router.resolve_route("model:openai-main:gpt-image-1", CTX, ("image_generation",))

        assert refused.value.code == "MODEL_CAPABILITY_UNAVAILABLE"
        assert refused.value.details["reason"] == "native_adapter"

    @pytest.mark.asyncio
    async def test_a_chat_call_is_not_judged_by_image_routes(self) -> None:
        router = _router(
            {
                "ark": _config(
                    "ark",
                    "doubao-seed",
                    kind="openai_compatible",
                    litellm_provider="volcengine",
                    capability_matrix={"chat": {"merged": True}},
                )
            }
        )

        route = await router.describe_route("model:ark:doubao-seed", CTX, ("chat",))

        assert route.port is not None


class TestGatewayPreflight:
    @pytest.mark.asyncio
    async def test_an_option_the_route_cannot_carry_is_refused(self) -> None:
        gateway = _gateway(_router({"openai-main": _config("openai-main", "gpt-image-1")}))

        with pytest.raises(KernelError) as refused:
            await gateway.check_image_request(
                "model:openai-main:gpt-image-1", operation="edit", seed=7, response_format="b64_json"
            )

        assert refused.value.code == "MODEL_IMAGE_CAPABILITY_UNAVAILABLE"
        assert refused.value.details == {
            "model": "model:openai-main:gpt-image-1",
            "capability": "seed",
            "param": "seed",
            "reason": "route_cannot_carry",
            "route": "OpenAIImageEditConfig",
        }

    @pytest.mark.asyncio
    async def test_what_the_route_carries_passes(self) -> None:
        gateway = _gateway(_router({"openai-main": _config("openai-main", "gpt-image-1")}))

        await gateway.check_image_request(
            "model:openai-main:gpt-image-1",
            operation="edit",
            n=2,
            has_mask=True,
            background="transparent",
            output_format="png",
            response_format="b64_json",
        )

    @pytest.mark.asyncio
    async def test_a_declared_trait_is_refused_with_its_reason(self) -> None:
        config = _config(
            "openai-main", "gpt-image-1", image_capabilities={"transparent_background": False}
        )
        gateway = _gateway(_router({"openai-main": config}))

        with pytest.raises(KernelError) as refused:
            await gateway.check_image_request(
                "model:openai-main:gpt-image-1", operation="generate", background="transparent"
            )

        assert refused.value.details["capability"] == "transparent_background"
        assert refused.value.details["reason"] == "declared"

    @pytest.mark.asyncio
    async def test_a_model_the_key_may_not_call_is_refused_first(self) -> None:
        looked_up: list[str] = []

        def resolve_provider(_ctx: RequestContext, slug: str, model_id: str) -> RuntimeProviderConfig:
            looked_up.append(slug)
            return _config(slug, model_id)

        router = LLMRouterPort(providers={}, provider_resolver=resolve_provider)
        ctx = RequestContext(
            tenant_id="t",
            workspace_id="w",
            user_id="u",
            workspace_role="Dev",
            allowed_models=frozenset({"model:other:model"}),
        )

        with pytest.raises(ForbiddenError):
            await _gateway(router, ctx).check_image_request(
                "model:openai-main:gpt-image-1", operation="edit", seed=7
            )

        assert looked_up == []

    @pytest.mark.asyncio
    async def test_it_spends_no_rate_or_quota_budget(self) -> None:
        limiter = MagicMock()
        limiter.check_rate_limit = AsyncMock()
        gateway = _gateway(
            _router({"openai-main": _config("openai-main", "gpt-image-1")}),
            rate_limit_per_minute=1,
            rate_limiter=limiter,
        )

        await gateway.check_image_request("model:openai-main:gpt-image-1", operation="generate")

        limiter.check_rate_limit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_route_that_does_not_resolve_is_left_to_the_call(self) -> None:
        # The call reports it as it always has: on a run, after admission.
        gateway = _gateway(_router({"openai-main": _config("openai-main", "gpt-image-1", status="disabled")}))

        await gateway.check_image_request("model:openai-main:gpt-image-1", operation="edit", seed=7)

    @pytest.mark.asyncio
    async def test_a_virtual_model_is_judged_by_the_targets_the_call_would_take(self) -> None:
        class _Targets:
            async def resolve_targets(self, _ctx: RequestContext, slug: str) -> list[str]:
                assert slug == "painter"
                return ["model:ark:doubao-seedream", "model:openai-main:gpt-image-1"]

        router = _router(
            {
                "ark": _config("ark", "doubao-seedream", kind="openai_compatible", litellm_provider="volcengine"),
                "openai-main": _config("openai-main", "gpt-image-1"),
            }
        )
        gateway = _gateway(router, virtual_models=_Targets())

        # The first target cannot edit at all and the last cannot carry a
        # seed, so the call would be refused by the last.
        with pytest.raises(KernelError) as refused:
            await gateway.check_image_request("vmodel:painter", operation="edit", seed=7)

        assert refused.value.details["model"] == "model:openai-main:gpt-image-1"
        assert refused.value.details["reason"] == "route_cannot_carry"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "targets",
        [
            ["model:openai-main:gpt-image-1", "model:stab:sd3-large"],
            ["model:stab:sd3-large", "model:openai-main:gpt-image-1"],
        ],
    )
    async def test_a_target_that_cannot_carry_an_option_is_passed_over(self, targets: list[str]) -> None:
        # Both targets resolve; Stability's edit carries a seed and OpenAI's
        # does not, so the request passes whichever comes first.
        class _Targets:
            async def resolve_targets(self, _ctx: RequestContext, _slug: str) -> list[str]:
                return targets

        router = _router(
            {
                "openai-main": _config("openai-main", "gpt-image-1"),
                "stab": _config("stab", "sd3-large", kind="openai_compatible", litellm_provider="stability"),
            }
        )

        await _gateway(router, virtual_models=_Targets()).check_image_request(
            "vmodel:painter", operation="edit", seed=7
        )

    @pytest.mark.asyncio
    async def test_when_no_target_carries_the_option_the_last_refusal_is_raised(self) -> None:
        class _Targets:
            async def resolve_targets(self, _ctx: RequestContext, _slug: str) -> list[str]:
                return ["model:openai-main:gpt-image-1", "model:openai-spare:dall-e-2"]

        router = _router(
            {
                "openai-main": _config("openai-main", "gpt-image-1"),
                "openai-spare": _config("openai-spare", "dall-e-2"),
            }
        )

        with pytest.raises(KernelError) as refused:
            await _gateway(router, virtual_models=_Targets()).check_image_request(
                "vmodel:painter", operation="edit", seed=7
            )

        assert refused.value.details["model"] == "model:openai-spare:dall-e-2"
        assert refused.value.details["reason"] == "route_cannot_carry"
