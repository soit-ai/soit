"""An image call whose answer never comes is still charged, as an estimate.

The provider was asked for the images and does not cancel the work when SOIT
stops waiting: a timed-out call may still be made and billed in full. So the
gateway charges it the count it asked for, flagged as estimated, and before
the provider is asked it makes that count durable on the step, so the charge
can still be told if the process making the call is gone.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llm.router import LLMRouterPort, RuntimeProviderConfig
from app.kernel.commons.errors import KernelError
from app.kernel.commons.errors import TimeoutError as KernelTimeoutError
from app.kernel.ports.llm.interface import (
    GeneratedImage,
    ImageGenerationResponse,
    LLMPort,
)
from app.kernel.ports.llm.policy import LLMPolicyGateway
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings

MODEL = "model:painter:gpt-image-1"


@pytest.fixture(autouse=True)
def _development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")

    async def allow_egress(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(GovernedEgressGuard, "authorize", allow_egress)


class _Provider(LLMPort):
    """Answers after a delay, or fails with an error of its own."""

    def __init__(self, *, delay: float = 0.0, error: Exception | None = None) -> None:
        self.delay = delay
        self.error = error
        self.asked = 0

    async def chat(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError

    async def embed(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError

    async def rerank(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - unused
        raise NotImplementedError

    async def _answer(self, n: int, model: str) -> ImageGenerationResponse:
        self.asked += 1
        await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return ImageGenerationResponse(images=[GeneratedImage(b64_json="aGk=") for _ in range(n)], model=model)

    async def generate_image(self, prompt: str, model: str, n: int = 1, size: str | None = None, **kwargs: Any):
        return await self._answer(n, model)

    async def edit_image(self, image: bytes, prompt: str, model: str, mask: bytes | None = None, n: int = 1, size: str | None = None, **kwargs: Any):
        return await self._answer(n, model)


def _config(slug: str, model_id: str, **overrides: Any) -> RuntimeProviderConfig:
    values: dict[str, Any] = {
        "provider_id": f"prov_{slug}",
        "slug": slug,
        "kind": "openai_compatible",
        "adapter_backend": "litellm",
        "status": "active",
        "provider_model_id": model_id,
        "model_id": model_id,
        "model_status": "active",
        "capability_matrix": {"image_generation": {"merged": True}, "image_edit": {"merged": True}},
        "pricing": {"currency": "USD", "image": "0.04"},
    }
    values.update(overrides)
    return RuntimeProviderConfig(**values)


def _writer(provider: _Provider) -> tuple[MagicMock, list[str]]:
    """A trace writer that records the order of the note, the commits and the provider call."""
    order: list[str] = []
    writer = MagicMock()
    step = MagicMock()
    step.id = "step_image"
    writer.create_step = AsyncMock(return_value=step)

    async def update_step_status(_step_id: str, _status: str, **kwargs: Any) -> None:
        if (kwargs.get("metrics") or {}).get("requested_images") is not None:
            order.append("note")

    writer.update_step_status = AsyncMock(side_effect=update_step_status)
    writer.record_cost = AsyncMock()
    writer.release_before_wait = AsyncMock(side_effect=lambda: order.append(f"commit:{provider.asked}"))
    capture = MagicMock()
    capture.keeps_content = True
    writer.content_capture = AsyncMock(return_value=capture)
    return writer, order


def _gateway(ctx: Any, provider: _Provider, writer: MagicMock, *, resolve: Any = None, **config: Any) -> LLMPolicyGateway:
    router = LLMRouterPort(
        providers={},
        provider_resolver=resolve or (lambda _ctx, slug, model_id: _config(slug, model_id, **config)),
        litellm_factory=lambda _config, _credentials: provider,
    )
    return LLMPolicyGateway(router, ctx, trace_writer=writer, image_timeout_seconds=0.02, max_retries=0)


async def _call(gateway: LLMPolicyGateway, operation: str, **kwargs: Any) -> Any:
    if operation == "edit":
        return await gateway.edit_image(image=b"png", prompt="a red dot", model=MODEL, run_id="run_image", **kwargs)
    return await gateway.generate_image(prompt="a red dot", model=MODEL, run_id="run_image", **kwargs)


def _noted(writer: MagicMock) -> list[dict[str, Any]]:
    return [
        c.kwargs["metrics"]
        for c in writer.update_step_status.await_args_list
        if c.args[1] == "running" and (c.kwargs.get("metrics") or {}).get("requested_images") is not None
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("operation", "billed_as"), [("generate", "generate_image"), ("edit", "edit_image")])
async def test_a_timed_out_image_call_is_charged_the_images_it_asked_for(ctx, operation, billed_as) -> None:
    provider = _Provider(delay=0.5)
    writer, _order = _writer(provider)

    with pytest.raises(KernelError) as timed_out:
        await _call(_gateway(ctx, provider, writer), operation, n=3, size="1024x1024")

    assert timed_out.value.code == "TIMEOUT"
    assert len(_noted(writer)) == 1
    writer.record_cost.assert_awaited_once()
    charge = writer.record_cost.await_args.kwargs
    assert charge["run_id"] == "run_image"
    assert charge["step_id"] == "step_image"
    assert charge["billing_basis"] == "images"
    assert charge["billed_quantity"] == 3
    assert charge["request_count"] == 3
    assert charge["operation"] == billed_as
    assert charge["currency"] == "USD"
    assert Decimal(str(charge["amount"])) == Decimal("0.12")
    assert charge["latency_ms"] >= 0
    assert charge["model_ref"] == MODEL
    assert (charge["provider_id"], charge["provider_slug"]) == ("prov_painter", "painter")
    snapshot = charge["pricing_snapshot_json"]
    assert snapshot["usage_estimated"] is True
    assert snapshot["usage_estimate_basis"] == "requested_images"
    assert snapshot["quantities"] == {"images": 3, "size": "1024x1024"}
    assert snapshot["model"]["requested"] == MODEL
    failed = writer.update_step_status.await_args_list[-1]
    assert failed.args[1] == "failed"
    assert failed.kwargs["metrics"] == {"usage_estimated": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["generate", "edit"])
async def test_the_request_is_made_durable_before_the_provider_is_asked(ctx, operation) -> None:
    provider = _Provider()
    writer, order = _writer(provider)

    await _call(_gateway(ctx, provider, writer), operation, n=2)

    (noted,) = _noted(writer)
    assert noted == {
        "requested_images": 2,
        "image_edit": operation == "edit",
        "model": MODEL,
        "model_ref": MODEL,
        "provider_id": "prov_painter",
        "provider_slug": "painter",
        "provider_kind": "openai_compatible",
    }
    # Committed right after it was noted, while the provider had not yet been asked.
    assert order[order.index("note") + 1] == "commit:0"


@pytest.mark.asyncio
async def test_an_answered_call_is_charged_what_came_back(ctx) -> None:
    provider = _Provider()
    writer, _order = _writer(provider)

    await _call(_gateway(ctx, provider, writer), "generate", n=2)

    charge = writer.record_cost.await_args.kwargs
    assert charge["billed_quantity"] == 2
    assert "usage_estimated" not in charge["pricing_snapshot_json"]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["generate", "edit"])
async def test_a_provider_that_answers_with_an_error_is_not_charged(ctx, operation) -> None:
    provider = _Provider(error=RuntimeError("provider refused the request"))
    writer, _order = _writer(provider)

    with pytest.raises(RuntimeError):
        await _call(_gateway(ctx, provider, writer), operation, n=2)

    writer.record_cost.assert_not_awaited()
    assert writer.update_step_status.await_args_list[-1].kwargs["metrics"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["generate", "edit"])
async def test_a_call_refused_before_the_provider_is_not_charged(ctx, operation) -> None:
    provider = _Provider()
    writer, _order = _writer(provider)
    gateway = _gateway(ctx, provider, writer, image_capabilities={"transparent_background": False})

    with pytest.raises(KernelError):
        await _call(gateway, operation, n=2, background="transparent")

    assert provider.asked == 0
    writer.record_cost.assert_not_awaited()
    assert _noted(writer) == []


@pytest.mark.asyncio
async def test_a_timeout_before_the_provider_is_asked_is_not_charged(ctx) -> None:
    # Timing out while the route is still being found costs nothing upstream.
    provider = _Provider()
    writer, _order = _writer(provider)

    def slow_resolver(*_args: Any) -> RuntimeProviderConfig:
        raise KernelTimeoutError("provider configuration timed out")

    with pytest.raises(KernelError):
        await _call(_gateway(ctx, provider, writer, resolve=slow_resolver), "generate", n=2)

    assert provider.asked == 0
    writer.record_cost.assert_not_awaited()


_PRICED_BY_QUALITY = {
    "currency": "USD",
    "image": "0.042",
    "image_variants": [{"quality": "high", "price": "0.167"}, {"quality": "high", "size": "1536x1024", "price": "0.25"}],
}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["generate", "edit"])
async def test_the_note_keeps_the_size_and_quality_a_price_can_depend_on(ctx, operation) -> None:
    provider = _Provider()
    writer, _order = _writer(provider)

    await _call(_gateway(ctx, provider, writer), operation, n=1, size="1536x1024", quality="high")

    (noted,) = _noted(writer)
    assert (noted["image_size"], noted["image_quality"]) == ("1536x1024", "high")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["generate", "edit"])
async def test_a_timed_out_call_is_charged_at_its_qualitys_price(ctx, operation) -> None:
    provider = _Provider(delay=0.5)
    writer, _order = _writer(provider)

    with pytest.raises(KernelError):
        await _call(
            _gateway(ctx, provider, writer, pricing=_PRICED_BY_QUALITY),
            operation,
            n=2,
            size="1536x1024",
            quality="high",
        )

    charge = writer.record_cost.await_args.kwargs
    assert Decimal(str(charge["amount"])) == Decimal("0.50")
    snapshot = charge["pricing_snapshot_json"]
    assert snapshot["image_variant"] == {"quality": "high", "size": "1536x1024"}
    assert snapshot["quantities"]["quality"] == "high"
    assert snapshot["usage_estimated"] is True
