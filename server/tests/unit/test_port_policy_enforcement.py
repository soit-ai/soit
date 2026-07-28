""" test_port_policy_enforcement

Comprehensive port policy enforcement tests.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from tenacity import RetryError

from app.kernel.commons.errors import ForbiddenError, TimeoutError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatMessage, ChatResponse, ChatStreamChunk
from app.kernel.ports.llm.policy import LLMPolicyGateway
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.runtime.runs.writer import TraceWriter


@pytest.fixture
def request_ctx() -> RequestContext:
    """Create request context."""
    return RequestContext(
        tenant_id="tenant_1",
        workspace_id="workspace_1",
        user_id="user_1",
        tenant_role="Owner",
        workspace_role="Owner",
    )


@pytest.fixture
def mock_llm_port():
    """Create mock LLM port."""
    port = AsyncMock()
    port.chat = AsyncMock(
        return_value=ChatResponse(
            text="response",
            tokens_prompt=10,
            tokens_completion=20,
            model="gpt-4",
        )
    )
    return port


@pytest.fixture
def mock_trace_writer():
    """Create mock trace writer."""
    writer = MagicMock(spec=TraceWriter)
    mock_step = MagicMock()
    mock_step.id = "step_123"
    writer.create_step = MagicMock(return_value=mock_step)
    writer.update_step_status = MagicMock()
    writer.record_cost = MagicMock()
    return writer


class FakeRateLimiter:
    """In-memory rate limiter for tests."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        if count > limit:
            raise ForbiddenError("Rate limit exceeded", {"limit": limit, "window_seconds": window_seconds})
        return True


@pytest.mark.asyncio
async def test_rate_limit_enforcement(request_ctx, mock_llm_port, mock_trace_writer):
    """Test that rate limits are enforced."""
    # Create policy gateway with strict rate limit
    policy = LLMPolicyGateway(
        gateway=mock_llm_port,
        ctx=request_ctx,
        trace_writer=mock_trace_writer,
        rate_limit_per_minute=2,
        rate_limiter=FakeRateLimiter(),
    )

    # First 2 calls should succeed
    await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_1")
    await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_1")

    # Third call should fail with rate limit
    with pytest.raises(ForbiddenError) as exc_info:
        await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_1")

    assert "rate limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_timeout_enforcement(request_ctx, mock_trace_writer):
    """Test that timeouts are enforced."""
    # Create slow mock port
    slow_port = AsyncMock()

    async def slow_chat(*_args, **_kwargs):
        import asyncio
        await asyncio.sleep(2)  # 2 seconds delay
        return ChatResponse(text="response", tokens_prompt=10, tokens_completion=20)

    slow_port.chat = slow_chat

    # Create policy with 1 second timeout
    policy = LLMPolicyGateway(
        gateway=slow_port,
        ctx=request_ctx,
        trace_writer=mock_trace_writer,
        timeout_seconds=1,
    )

    # Should timeout
    with pytest.raises(TimeoutError):
        await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_timeout")


@pytest.mark.asyncio
async def test_audit_logging(request_ctx, mock_llm_port, mock_trace_writer):
    """Test that all calls are audited via trace writer."""
    policy = LLMPolicyGateway(
        gateway=mock_llm_port,
        ctx=request_ctx,
        trace_writer=mock_trace_writer,
    )

    await policy.chat(
        model="gpt-4",
        messages=[ChatMessage("user", "test message")],
        run_id="run_123",
    )

    # Verify trace writer was called
    mock_trace_writer.create_step.assert_called_once()
    call_args = mock_trace_writer.create_step.call_args
    assert call_args[1]["run_id"] == "run_123"
    assert call_args[1]["step_type"] == "llm"

    # Verify step status updates
    mock_trace_writer.update_step_status.assert_called()

    # One metered invocation records exactly one usage row carrying latency.
    assert mock_trace_writer.record_cost.call_count == 1
    token_call = mock_trace_writer.record_cost.call_args_list[0]
    assert token_call.kwargs["unit"] == "tokens"
    assert token_call.kwargs["quantity"] == 30
    assert token_call.kwargs["latency_ms"] is not None
    assert token_call.kwargs["source_port"] == "llm"
    assert token_call.kwargs["operation"] == "chat"


@pytest.mark.asyncio
async def test_retry_on_failure(request_ctx, mock_trace_writer):
    """Test that retries are attempted on transient failures."""
    # Create port that fails twice then succeeds
    retry_port = AsyncMock()
    call_count = 0

    async def failing_chat(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Transient error")
        return ChatResponse(text="success", tokens_prompt=10, tokens_completion=20)

    retry_port.chat = failing_chat

    policy = LLMPolicyGateway(
        gateway=retry_port,
        ctx=request_ctx,
        trace_writer=mock_trace_writer,
        max_retries=3,
    )

    # Should succeed after retries
    result = await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_retry")
    assert result.text == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_max_retries_counts_additional_attempts(request_ctx):
    port = AsyncMock()
    port.chat = AsyncMock(side_effect=ConnectionError("upstream unavailable"))
    policy = LLMPolicyGateway(
        gateway=port,
        ctx=request_ctx,
        max_retries=2,
        retry_backoff_base_seconds=0,
    )

    with pytest.raises(ConnectionError, match="upstream unavailable"):
        await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")])

    assert port.chat.await_count == 3


@pytest.mark.asyncio
async def test_validation_errors_are_not_retried(request_ctx):
    port = AsyncMock()
    port.chat = AsyncMock(side_effect=ValidationError("invalid model parameters"))
    policy = LLMPolicyGateway(
        gateway=port,
        ctx=request_ctx,
        max_retries=3,
        retry_backoff_base_seconds=0,
    )

    with pytest.raises(ValidationError, match="invalid model parameters"):
        await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")])

    assert port.chat.await_count == 1


@pytest.mark.asyncio
async def test_stream_retries_only_before_first_chunk(request_ctx):
    attempts = 0

    class FlakyStreamPort:
        async def stream_chat(self, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ConnectionError("failed before first chunk")
            yield ChatStreamChunk(delta="ok")
            yield ChatStreamChunk(done=True, finish_reason="stop")

    policy = LLMPolicyGateway(
        gateway=FlakyStreamPort(),
        ctx=request_ctx,
        max_retries=1,
        retry_backoff_base_seconds=0,
    )

    chunks = [
        chunk
        async for chunk in policy.stream_chat(
            model="gpt-4",
            messages=[ChatMessage("user", "test")],
        )
    ]

    assert attempts == 2
    assert "".join(chunk.delta for chunk in chunks) == "ok"


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_first_chunk(request_ctx):
    attempts = 0

    class MidStreamFailurePort:
        async def stream_chat(self, **kwargs):
            nonlocal attempts
            attempts += 1
            yield ChatStreamChunk(delta="partial")
            raise ConnectionError("failed after first chunk")

    policy = LLMPolicyGateway(
        gateway=MidStreamFailurePort(),
        ctx=request_ctx,
        max_retries=3,
        retry_backoff_base_seconds=0,
    )

    with pytest.raises(ConnectionError, match="failed after first chunk"):
        _ = [
            chunk
            async for chunk in policy.stream_chat(
                model="gpt-4",
                messages=[ChatMessage("user", "test")],
            )
        ]

    assert attempts == 1


@pytest.mark.asyncio
async def test_cost_tracking_accuracy(request_ctx, mock_llm_port, mock_trace_writer):
    """Test that costs are tracked accurately."""
    mock_llm_port.chat.return_value = ChatResponse(
        text="response",
        tokens_prompt=100,
        tokens_completion=200,
        model="gpt-4",
    )

    policy = LLMPolicyGateway(
        gateway=mock_llm_port,
        ctx=request_ctx,
        trace_writer=mock_trace_writer,
    )

    await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_cost")

    # Verify cost recording
    token_call = next(
        call for call in mock_trace_writer.record_cost.call_args_list if call.kwargs.get("unit") == "tokens"
    )
    assert token_call.kwargs["quantity"] == 300
    assert token_call.kwargs["prompt_tokens"] == 100
    assert token_call.kwargs["completion_tokens"] == 200
    assert token_call.kwargs["model_ref"] == "gpt-4"


@pytest.mark.asyncio
async def test_tool_secret_injection_isolation(request_ctx):
    """Test that secrets are injected per tenant and not leaked."""
    # Mock tool port
    mock_tool_port = AsyncMock()
    mock_tool_port.invoke = AsyncMock(
        return_value=ToolResponse(result="success", success=True, metadata={})
    )

    # Mock secrets provider
    mock_secrets = AsyncMock()
    mock_secrets.get_secret = AsyncMock(return_value="tenant_1_secret")

    policy = ToolPolicyGateway(
        gateway=mock_tool_port,
        ctx=request_ctx,
        secrets_port=mock_secrets,
        enable_egress_check=False,
    )

    await policy.invoke(
        tool_ref="tool:http:demo",
        parameters={"input": {"secret_id": "sec_demo"}},
        run_id="run_123",
    )

    # Verify secrets were requested for correct tenant
    mock_secrets.get_secret.assert_called()
    call_args = mock_secrets.get_secret.call_args
    assert call_args.kwargs["secret_id"] == "sec_demo"


@pytest.mark.asyncio
async def test_tool_policy_does_not_retry_a_durable_agent_invocation(request_ctx):
    attempts = 0

    class SideEffectingTool:
        async def invoke(self, tool_ref, parameters, **kwargs):
            nonlocal attempts
            attempts += 1
            raise RuntimeError("response lost after side effect")

    policy = ToolPolicyGateway(
        gateway=SideEffectingTool(),
        ctx=request_ctx,
        max_retries=2,
        enable_egress_check=False,
    )

    with pytest.raises(RetryError):
        await policy.invoke(
            tool_ref="tool:function:side_effect",
            parameters={"value": "once"},
            run_id="run_side_effect_once",
            idempotency_key="agent-tool:run_side_effect_once:call_once",
        )

    assert attempts == 1


def test_tool_policy_exposes_builtin_registration_for_agent_resolution(request_ctx):
    class BuiltinToolGateway:
        def __init__(self):
            self.registered = []

        def register_builtin(self, tool_ref, ctx):
            self.registered.append((tool_ref, ctx))
            return True

        async def invoke(self, tool_ref, parameters, **kwargs):
            return ToolResponse(result={}, success=True, metadata={})

    inner = BuiltinToolGateway()
    policy = ToolPolicyGateway(
        gateway=inner,
        ctx=request_ctx,
        enable_egress_check=False,
    )

    assert policy.register_builtin("tool:function:time_now", request_ctx) is True
    assert inner.registered == [("tool:function:time_now", request_ctx)]


@pytest.mark.asyncio
async def test_concurrent_policy_enforcement(request_ctx, mock_llm_port, mock_trace_writer):
    """Test that policies are enforced correctly under concurrent load."""
    import asyncio

    policy = LLMPolicyGateway(
        gateway=mock_llm_port,
        ctx=request_ctx,
        trace_writer=mock_trace_writer,
        rate_limit_per_minute=10,
        rate_limiter=FakeRateLimiter(),
    )

    # Make 5 concurrent calls
    tasks = [
        policy.chat(model="gpt-4", messages=[ChatMessage("user", f"test {i}")], run_id="run_concurrent")
        for i in range(5)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # All should succeed (within rate limit)
    for result in results:
        assert not isinstance(result, Exception)
        assert result.text == "response"


@pytest.mark.asyncio
async def test_policy_bypass_prevention(request_ctx, mock_llm_port, mock_trace_writer):
    """Test that policy cannot be bypassed by direct port access."""
    # This test ensures that modules MUST use policy gateway, not raw port

    policy = LLMPolicyGateway(
        gateway=mock_llm_port,
        ctx=request_ctx,
        trace_writer=mock_trace_writer,
        rate_limit_per_minute=1,
        rate_limiter=FakeRateLimiter(),
    )

    # First call through policy (uses quota)
    await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_bypass")

    # Second call through policy should fail
    with pytest.raises(ForbiddenError):
        await policy.chat(model="gpt-4", messages=[ChatMessage("user", "test")], run_id="run_bypass")

    # Verify that even if someone tries to bypass policy by using inner_port,
    # the rate limit state is maintained (this is a design verification)
    # Note: In real code, inner_port should not be exposed
    assert hasattr(policy, "gateway")
    assert not hasattr(policy, "inner_port")
