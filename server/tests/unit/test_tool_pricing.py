"""A tool call is priced from the per-call price its ToolSpec declares."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import select

from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.ports.tools.pricing import declared_call_pricing
from app.kernel.runtime.db.models.runs import RunCostEntry
from app.kernel.runtime.runs.writer import TraceWriter

TOOL = "tool:function:web_search"


def test_a_declared_price_prices_one_call() -> None:
    pricing = declared_call_pricing({"pricing": {"currency": "USD", "call": "0.002"}}, tool_ref=TOOL)

    assert (pricing.currency, pricing.amount) == ("USD", Decimal("0.002"))
    assert pricing.snapshot["priced"] is True
    assert pricing.snapshot["rates"]["call"]["price"] == "0.002"
    assert pricing.snapshot["tool_ref"] == TOOL


def test_a_declared_zero_is_a_price_not_a_missing_one() -> None:
    pricing = declared_call_pricing({"pricing": {"currency": "USD", "call": "0"}}, tool_ref=TOOL)

    assert (pricing.currency, pricing.amount) == ("USD", Decimal("0"))
    assert pricing.snapshot["priced"] is True


def test_a_tool_without_a_price_is_unpriced_and_says_so() -> None:
    pricing = declared_call_pricing({"audit_level": "basic"}, tool_ref=TOOL)

    assert (pricing.currency, pricing.amount) == (None, None)
    assert pricing.snapshot["reason"] == "tool_pricing_not_declared"


@pytest.mark.parametrize(
    "configured",
    [
        {"currency": "usd", "call": "1"},
        {"currency": "USD", "call": 0.002},
        {"currency": "USD", "call": "-1"},
        {"currency": "USD", "call": "1.1234567"},
        {"currency": "USD", "call": "1234567890123"},
        {"currency": "USD", "call": "NaN"},
        {"currency": "USD"},
        {"currency": "USD", "call": "1", "per": "month"},
        {"currency": "USD", "call": 2},
        {"currency": "USD", "call": "-0"},
        {"currency": "USD", "call": "1e3"},
        {"currency": "USD", "call": "+5"},
        {"currency": "USD", "call": " 0.5 "},
        {"currency": "USD", "call": "007"},
        "0.002",
    ],
)
def test_a_price_that_cannot_be_read_is_never_taken_as_zero(configured: Any) -> None:
    pricing = declared_call_pricing({"pricing": configured}, tool_ref=TOOL)

    assert (pricing.currency, pricing.amount) == (None, None)
    assert pricing.snapshot["reason"] == "unsupported_pricing_config"


class _Tools:
    """A tool gateway whose one tool declares the given policy."""

    def __init__(self, policy: dict[str, Any], *, succeed: bool = True) -> None:
        self.policy = policy
        self.succeed = succeed
        self.kwargs: list[dict[str, Any]] = []

    def get_tool_policy(self, tool_ref: str, ctx: Any) -> dict[str, Any]:
        del tool_ref, ctx
        return self.policy

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        del tool_ref, parameters
        self.kwargs.append(kwargs)
        if not self.succeed:
            return ToolResponse(result=None, success=False, error="All connection attempts failed")
        return ToolResponse(result={"hits": 3})


async def _call(async_db, ctx, tools: _Tools, *, ref: str = TOOL, **kwargs: Any) -> list[RunCostEntry]:
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")
    gateway = ToolPolicyGateway(gateway=tools, ctx=ctx, trace_writer=writer, enable_egress_check=False)
    for _ in range(kwargs.pop("times", 1)):
        response = await gateway.invoke(ref, {"q": "refunds"}, run_id=run.id, **kwargs)
        assert response.success is tools.succeed
    return list((await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run.id))).all())


@pytest.mark.asyncio
async def test_a_call_is_priced_from_its_own_toolspec(async_db, ctx) -> None:
    tools = _Tools({"audit_level": "basic", "pricing": {"currency": "USD", "call": "0.002"}})

    [cost] = await _call(async_db, ctx, tools)

    assert (cost.amount, cost.currency, cost.tool_ref) == (Decimal("0.002"), "USD", TOOL)
    assert cost.pricing_snapshot_json["source"] == "tool_spec"


@pytest.mark.asyncio
async def test_the_policy_a_caller_resolved_prices_the_call(async_db, ctx) -> None:
    tools = _Tools({"audit_level": "basic"})

    [cost] = await _call(
        async_db, ctx, tools, tool_policy={"pricing": {"currency": "USD", "call": "0.005"}}
    )

    assert cost.amount == Decimal("0.005")
    # It prices the call and goes no further.
    assert all("tool_policy" not in kwargs for kwargs in tools.kwargs)


@pytest.mark.asyncio
async def test_a_call_to_an_unpriced_tool_is_recorded_unpriced(async_db, ctx) -> None:
    [cost] = await _call(async_db, ctx, _Tools({"audit_level": "basic"}))

    assert (cost.amount, cost.currency) == (None, None)
    assert cost.pricing_snapshot_json["reason"] == "tool_pricing_not_declared"


@pytest.mark.asyncio
async def test_a_broken_price_never_fails_a_call_that_ran(async_db, ctx) -> None:
    tools = _Tools({"audit_level": "basic", "pricing": {"currency": "USD", "call": 0.1}})

    [cost] = await _call(async_db, ctx, tools)

    assert cost.amount is None
    assert cost.pricing_snapshot_json["reason"] == "unsupported_pricing_config"


@pytest.mark.asyncio
async def test_a_replayed_call_is_charged_once(async_db, ctx) -> None:
    tools = _Tools({"audit_level": "basic", "pricing": {"currency": "USD", "call": "0.002"}})

    costs = await _call(async_db, ctx, tools, times=2, idempotency_key="order-42", tool_call_id="call_42")

    assert [cost.amount for cost in costs] == [Decimal("0.002")]
    assert len(tools.kwargs) == 1


@pytest.mark.asyncio
async def test_a_failed_call_is_not_charged(async_db, ctx) -> None:
    tools = _Tools({"audit_level": "basic", "pricing": {"currency": "USD", "call": "0.5"}}, succeed=False)

    [cost] = await _call(async_db, ctx, tools)

    assert (cost.amount, cost.currency) == (None, None)
    assert cost.pricing_snapshot_json["reason"] == "tool_call_failed"


@pytest.mark.asyncio
async def test_an_mcp_tool_whose_policy_was_not_passed_says_so(async_db, ctx) -> None:
    [cost] = await _call(async_db, ctx, _Tools({}), ref="mcp_tool:search:web")

    assert cost.amount is None
    assert cost.pricing_snapshot_json["reason"] == "tool_pricing_not_resolved"


@pytest.mark.asyncio
async def test_the_agent_hands_the_gateway_the_policy_it_resolved() -> None:
    from unittest.mock import AsyncMock

    from app.modules.agent.runtime.executor import AgentExecutor

    tools = AsyncMock()
    executor = AgentExecutor(tools)
    policy = {"pricing": {"currency": "USD", "call": "0.01"}}

    await executor.execute_tool(
        tool_ref="mcp_tool:search:web",
        parameters={},
        ctx=object(),  # type: ignore[arg-type]
        run_id="run_1",
        tool_call_id="call_1",
        idempotency_key="tool:run_1:call_1",
        tool_policy=policy,
    )

    assert tools.invoke.await_args.kwargs["tool_policy"] is policy
