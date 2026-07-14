""" test_gateway_timeout

Unit tests for gateway timeout functionality.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.kernel.commons.errors import TimeoutError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatMessage, ChatResponse, LLMPort
from app.kernel.ports.llm.policy import LLMPolicyGateway


@pytest.fixture
def mock_gateway():
    """Create mock LLM gateway."""
    gateway = MagicMock(spec=LLMPort)
    gateway.chat = AsyncMock(return_value=ChatResponse(text="test"))
    return gateway


@pytest.fixture
def ctx():
    """Create test context."""
    return RequestContext(
        tenant_id="test_tenant",
        workspace_id="test_workspace",
        user_id="test_user",
    )


@pytest.mark.asyncio
async def test_timeout_raises_error(mock_gateway, ctx):
    """Test that timeout raises TimeoutError."""
    # Make gateway slow
    async def slow_chat(*_args, **_kwargs):
        await asyncio.sleep(2)
        return ChatResponse(text="test")

    mock_gateway.chat = slow_chat

    policy_gateway = LLMPolicyGateway(
        gateway=mock_gateway,
        ctx=ctx,
        timeout_seconds=1,  # 1 second timeout
    )

    with pytest.raises(TimeoutError):
        await policy_gateway.chat(
            messages=[ChatMessage(role="user", content="test")],
            model="model:openai:gpt-4",
        )


@pytest.mark.asyncio
async def test_no_timeout_on_fast_request(mock_gateway, ctx):
    """Test that fast requests don't timeout."""
    policy_gateway = LLMPolicyGateway(
        gateway=mock_gateway,
        ctx=ctx,
        timeout_seconds=10,
    )

    response = await policy_gateway.chat(
        messages=[ChatMessage(role="user", content="test")],
        model="model:openai:gpt-4",
    )

    assert response.text == "test"
