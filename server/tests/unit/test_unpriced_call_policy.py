"""A call no price applies to counts against no budget; the workspace may refuse it.

The guard answers by the workspace's policy: ``allow`` lets the call through,
``refuse_when_budgeted`` refuses it while a hard-stop budget applies to it, and
``refuse`` always does. The gateways ask once a target is known, before the
provider or the tool is called, and a virtual model moves on to a priced target.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.kernel.commons.errors import KernelError, UnpricedCallRefusedError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    GeneratedImage,
    ImageGenerationResponse,
    LLMRuntimeTarget,
)
from app.kernel.ports.llm.policy import LLMPolicyGateway
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.modules.billing.application.budgets import BudgetGuard, CompositeCreditGuard
from app.modules.billing.domain.models import Budget

CTX = RequestContext(tenant_id="t1", workspace_id="w1", user_id="u1", request_id="r1")
MESSAGES = [ChatMessage(role="user", content="hi")]
PRICED = {"currency": "USD", "input": 1, "input_unit": "1m_tokens", "output": 2, "output_unit": "1m_tokens"}
UNPRICED_REF = "model:local:llama"
PRICED_REF = "model:cloud:gpt"


# --- the guard -------------------------------------------------------------


class _Recorder:
    def __init__(self) -> None:
        self.unpriced: list[dict[str, Any]] = []

    async def record_block(self, ctx: RequestContext, *, details: dict[str, Any]) -> None:
        del ctx, details

    async def record_unpriced_block(self, ctx: RequestContext, *, details: dict[str, Any]) -> None:
        del ctx
        self.unpriced.append(details)


def _guard(async_db, ctx: RequestContext, policy: str | None, recorder: _Recorder | None = None) -> BudgetGuard:
    async def lookup() -> str:
        return policy or "allow"

    return BudgetGuard(async_db, ctx, recorder=recorder, unpriced_policy=lookup if policy else None)


async def _ask(guard: Any) -> None:
    await guard.check_unpriced(operation="chat", run_id=None, ref=UNPRICED_REF, reason="pricing_not_configured")


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [None, "allow"])
async def test_an_unpriced_call_goes_ahead_by_default(async_db, ctx, policy) -> None:
    await _ask(_guard(async_db, ctx, policy))


@pytest.mark.asyncio
async def test_refuse_refuses_and_audits_it(async_db, ctx) -> None:
    recorder = _Recorder()

    with pytest.raises(UnpricedCallRefusedError) as refused:
        await _ask(_guard(async_db, ctx, "refuse", recorder))

    assert refused.value.code == "PRICING_NOT_CONFIGURED"
    assert refused.value.details["policy"] == "refuse"
    assert refused.value.details["pricing_reason"] == "pricing_not_configured"
    assert UNPRICED_REF in str(refused.value)
    assert recorder.unpriced[0]["ref"] == UNPRICED_REF


@pytest.mark.asyncio
async def test_refuse_when_budgeted_refuses_only_under_a_hard_stop_budget(async_db, ctx) -> None:
    await _ask(_guard(async_db, ctx, "refuse_when_budgeted"))

    soft = Budget(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="Soft",
        amount=Decimal("10"),
        currency="USD",
        hard_stop=False,
        created_by=ctx.user_id,
    )
    async_db.add(soft)
    await async_db.commit()
    await _ask(_guard(async_db, ctx, "refuse_when_budgeted"))

    hard = Budget(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="Team",
        amount=Decimal("10"),
        currency="USD",
        created_by=ctx.user_id,
    )
    async_db.add(hard)
    await async_db.commit()
    with pytest.raises(UnpricedCallRefusedError) as refused:
        await _ask(_guard(async_db, ctx, "refuse_when_budgeted"))

    assert refused.value.details["budget_ids"] == [hard.id]
    assert "Team" in str(refused.value)


@pytest.mark.asyncio
async def test_the_composite_guard_asks_every_guard_that_can_answer(async_db, ctx) -> None:
    class _Credit:
        async def check(self, *, operation: str, run_id: str | None = None) -> None:
            del operation, run_id

    with pytest.raises(UnpricedCallRefusedError):
        await _ask(CompositeCreditGuard(_Credit(), _guard(async_db, ctx, "refuse")))


# --- the model gateway ------------------------------------------------------


class _Refusing:
    """A spend guard whose workspace refuses every unpriced call."""

    def __init__(self, refuse: bool = True) -> None:
        self.refuse = refuse
        self.asked: list[tuple[str, str, str]] = []

    async def check(self, *, operation: str, run_id: str | None = None) -> None:
        del operation, run_id

    async def check_unpriced(self, *, operation: str, run_id: str | None, ref: str, reason: str) -> None:
        del run_id
        self.asked.append((operation, ref, reason))
        if self.refuse:
            raise UnpricedCallRefusedError(f"No price for {ref}", {"pricing_reason": reason, "ref": ref})


class _Port:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []

    async def chat(self, *, model: str, **kwargs: Any) -> ChatResponse:
        del kwargs
        self.calls.append(model)
        return ChatResponse(text=self.name, tokens_prompt=3, tokens_completion=2, model=self.name)

    async def stream_chat(self, *, model: str, **kwargs: Any) -> AsyncIterator[ChatStreamChunk]:
        del kwargs
        self.calls.append(model)
        yield ChatStreamChunk(delta=self.name, model=self.name)
        yield ChatStreamChunk(done=True, finish_reason="stop", tokens_prompt=3, tokens_completion=2)

    async def generate_image(self, *, model: str, **kwargs: Any) -> ImageGenerationResponse:
        del kwargs
        self.calls.append(model)
        return ImageGenerationResponse(images=[GeneratedImage(b64_json="aGk=")], model=self.name)


class _Route:
    def __init__(self, port: _Port, model: str, pricing: dict[str, Any]) -> None:
        provider = model.split(":")[1]
        self.port = port
        self.target = LLMRuntimeTarget(
            provider_id=f"prov_{provider}",
            provider_slug=provider,
            provider_kind="openai",
            adapter_backend="native",
            model_ref=model,
            model_id=model.split(":")[2],
        )
        self.timeout_seconds = 5.0
        self.max_retries = 0
        self.retry_backoff = "none"
        self.retryable_status_codes = (500,)
        self.pricing = pricing
        self.image_capabilities: dict[str, Any] = {}


class _Router:
    def __init__(self, routes: dict[str, tuple[_Port, dict[str, Any]]]) -> None:
        self.routes = routes

    async def resolve_route(self, model: str, ctx: Any, required_capabilities: tuple[str, ...]) -> _Route:
        del ctx, required_capabilities
        if model not in self.routes:
            raise KernelError("MODEL_RUNTIME_DISABLED", f"Workspace model is disabled: {model}")
        port, pricing = self.routes[model]
        return _Route(port, model, pricing)

    def stream_chat(self, **kwargs: Any) -> Any:  # pragma: no cover - routed per target
        raise AssertionError("calls go through the resolved route")


class _VirtualModels:
    async def resolve_targets(self, ctx: RequestContext, slug: str) -> list[str] | None:
        del ctx
        return [UNPRICED_REF, PRICED_REF] if slug == "mixed" else None


def _writer() -> MagicMock:
    writer = MagicMock()
    step = MagicMock()
    step.id = "step_1"
    writer.create_step = AsyncMock(return_value=step)
    writer.update_step_status = AsyncMock()
    writer.record_cost = AsyncMock()
    writer.release_before_wait = AsyncMock()
    return writer


def _gateway(guard: _Refusing, writer: MagicMock | None = None) -> tuple[LLMPolicyGateway, _Port, _Port]:
    local, cloud = _Port("local"), _Port("cloud")
    gateway = LLMPolicyGateway(
        gateway=_Router({UNPRICED_REF: (local, {}), PRICED_REF: (cloud, PRICED)}),  # type: ignore[arg-type]
        ctx=CTX,
        trace_writer=writer,
        credit_guard=guard,
        retry_backoff_base_seconds=0,
        virtual_models=_VirtualModels(),
    )
    return gateway, local, cloud


@pytest.mark.asyncio
async def test_an_unpriced_model_is_refused_before_the_provider_is_called() -> None:
    guard = _Refusing()
    gateway, local, _ = _gateway(guard)

    with pytest.raises(UnpricedCallRefusedError):
        await gateway.chat(MESSAGES, UNPRICED_REF)

    assert local.calls == []
    assert guard.asked == [("chat", UNPRICED_REF, "pricing_not_configured")]


@pytest.mark.asyncio
async def test_a_priced_model_is_not_asked_about() -> None:
    guard = _Refusing()
    gateway, _, cloud = _gateway(guard)

    response = await gateway.chat(MESSAGES, PRICED_REF)

    assert response.text == "cloud"
    assert cloud.calls == [PRICED_REF]
    assert guard.asked == []


@pytest.mark.asyncio
async def test_an_allowed_unpriced_call_goes_ahead() -> None:
    guard = _Refusing(refuse=False)
    gateway, local, _ = _gateway(guard)

    response = await gateway.chat(MESSAGES, UNPRICED_REF)

    assert response.text == "local"
    assert local.calls == [UNPRICED_REF]


@pytest.mark.asyncio
async def test_a_virtual_model_moves_on_from_an_unpriced_target() -> None:
    writer = _writer()
    gateway, local, cloud = _gateway(_Refusing(), writer)

    response = await gateway.chat(MESSAGES, "vmodel:mixed", run_id="run_1")

    assert response.text == "cloud"
    assert (local.calls, cloud.calls) == ([], [PRICED_REF])
    attempts = writer.update_step_status.await_args.kwargs["metrics"]["attempts"]
    assert attempts[0] == {
        "model_ref": UNPRICED_REF,
        "outcome": "unavailable",
        "reason": "PRICING_NOT_CONFIGURED",
        "pricing_reason": "pricing_not_configured",
    }


@pytest.mark.asyncio
async def test_an_unpriced_stream_is_refused_before_its_first_chunk() -> None:
    gateway, local, _ = _gateway(_Refusing())

    with pytest.raises(UnpricedCallRefusedError):
        async for _ in gateway.stream_chat(MESSAGES, UNPRICED_REF):
            pass

    assert local.calls == []


@pytest.mark.asyncio
async def test_a_stream_moves_on_from_an_unpriced_target() -> None:
    gateway, local, cloud = _gateway(_Refusing())

    chunks = [chunk async for chunk in gateway.stream_chat(MESSAGES, "vmodel:mixed")]

    assert chunks[0].delta == "cloud"
    assert (local.calls, cloud.calls) == ([], [PRICED_REF])


@pytest.mark.asyncio
async def test_an_image_priced_only_at_another_quality_is_refused() -> None:
    guard = _Refusing()
    port = _Port("images")
    pricing = {"currency": "USD", "image_variants": [{"quality": "high", "price": "0.1"}]}
    gateway = LLMPolicyGateway(
        gateway=_Router({PRICED_REF: (port, pricing)}),  # type: ignore[arg-type]
        ctx=CTX,
        trace_writer=None,
        credit_guard=guard,
    )

    with pytest.raises(UnpricedCallRefusedError):
        await gateway.generate_image("a cat", PRICED_REF, quality="low")
    await gateway.generate_image("a cat", PRICED_REF, quality="high")

    assert [operation for operation, _, _ in guard.asked] == ["generate_image"]
    assert guard.asked[0][2] == "image_variant_not_priced"
    assert port.calls == [PRICED_REF]


# --- the tool gateway -------------------------------------------------------


class _Tools:
    def __init__(self, policy: dict[str, Any]) -> None:
        self.policy = policy
        self.invoked = 0

    def get_tool_policy(self, tool_ref: str, ctx: Any) -> dict[str, Any]:
        del tool_ref, ctx
        return self.policy

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        del tool_ref, parameters, kwargs
        self.invoked += 1
        return ToolResponse(result={"ok": True})


@pytest.mark.asyncio
async def test_a_tool_without_a_price_is_refused_before_it_runs() -> None:
    guard = _Refusing()
    tools = _Tools({"audit_level": "basic"})
    gateway = ToolPolicyGateway(gateway=tools, ctx=CTX, credit_guard=guard, enable_egress_check=False)

    with pytest.raises(UnpricedCallRefusedError):
        await gateway.invoke("tool:function:search", {"q": "x"})

    assert tools.invoked == 0
    assert guard.asked == [("tool", "tool:function:search", "tool_pricing_not_declared")]


@pytest.mark.asyncio
async def test_a_priced_tool_runs_without_asking() -> None:
    guard = _Refusing()
    tools = _Tools({"pricing": {"currency": "USD", "call": "0"}})
    gateway = ToolPolicyGateway(gateway=tools, ctx=CTX, credit_guard=guard, enable_egress_check=False)

    response = await gateway.invoke("tool:function:search", {"q": "x"})

    assert response.success is True
    assert tools.invoked == 1
    assert guard.asked == []
