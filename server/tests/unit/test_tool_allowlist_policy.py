"""A key limited to some tools reaches no other tool, from any entry."""

from __future__ import annotations

from typing import Any

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway

LIMITED = RequestContext(
    tenant_id="t",
    workspace_id="w",
    user_id="u",
    workspace_role="Dev",
    api_key_id="key_1",
    allowed_tools=frozenset({"tool:function:time_now"}),
)


class _Recorder(ToolPort):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.calls.append(tool_ref)
        return ToolResponse(result={"ok": True})


@pytest.mark.asyncio
async def test_the_gateway_refuses_a_tool_outside_the_keys_list() -> None:
    inner = _Recorder()
    gateway = ToolPolicyGateway(gateway=inner, ctx=LIMITED, enable_egress_check=False)

    with pytest.raises(ForbiddenError) as refused:
        await gateway.invoke("tool:http:request", {"url": "https://example.com"})
    response = await gateway.invoke("tool:function:time_now", {})

    assert refused.value.details["reason"] == "tool_not_allowed"
    assert inner.calls == ["tool:function:time_now"]
    assert response.success is True


def test_no_list_allows_every_tool() -> None:
    ctx = RequestContext(tenant_id="t", workspace_id="w", user_id="u")

    assert ctx.may_invoke_tool("tool:anything")
    assert not LIMITED.may_invoke_tool("tool:anything")
