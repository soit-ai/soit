"""SOIT answers MCP clients with one workspace's tools, statelessly."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

import pytest

from app.api.mcp.router import mcp_caller
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.db.models.runs import Run
from app.main import app
from app.settings.settings import settings

pytestmark = pytest.mark.asyncio

GATED = "tool:function:gated_random"
MCP_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@pytest.fixture(autouse=True)
def _caller(ctx):
    from app.wiring import get_container

    # The API builds the container at startup; the ASGI test transport runs no lifespan.
    get_container()
    app.dependency_overrides[mcp_caller] = lambda: ctx
    yield
    app.dependency_overrides.pop(mcp_caller, None)


def _as(ctx) -> None:
    app.dependency_overrides[mcp_caller] = lambda: ctx


def _register_gated_tool(ctx) -> None:
    get_registry().register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=GATED,
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "gated_random",
                "description": "A random integer.",
                "adapter": "function",
                "input_schema": {
                    "type": "object",
                    "properties": {"min": {"type": "integer"}, "max": {"type": "integer"}},
                    "required": ["min", "max"],
                },
                "output_schema": {"type": "object"},
                "policy": {"approval": {"mode": "required", "risk_level": "high"}},
                "function": {"entrypoint": "app.utils.builtin_tools:random_int"},
            }
        },
    )


async def _rpc(async_client, method: str, params: dict[str, Any] | None = None, **headers: str):
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 7, "method": method}
    if params is not None:
        body["params"] = params
    return await async_client.post("/mcp", json=body, headers=headers)


async def _tools(async_client) -> dict[str, dict[str, Any]]:
    response = await _rpc(async_client, "tools/list")
    assert response.status_code == 200, response.text
    return {tool["name"]: tool for tool in response.json()["result"]["tools"]}


async def test_initialize_negotiates_a_version_and_opens_no_session(async_client) -> None:
    response = await _rpc(
        async_client,
        "initialize",
        {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["jsonrpc"], body["id"]) == ("2.0", 7)
    result = body["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["capabilities"]["tools"] == {"listChanged": False}
    assert result["serverInfo"]["name"] == "soit"
    assert "mcp-session-id" not in response.headers

    newer = await _rpc(async_client, "initialize", {"protocolVersion": "2099-01-01", "capabilities": {}})
    from mcp.types import LATEST_PROTOCOL_VERSION

    assert newer.json()["result"]["protocolVersion"] == LATEST_PROTOCOL_VERSION


async def test_notifications_are_accepted_without_a_reply(async_client) -> None:
    response = await async_client.post(
        "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}
    )

    assert response.status_code == 202
    assert response.content == b""


async def test_the_tool_list_names_every_tool_the_way_clients_accept(async_client, ctx) -> None:
    _register_gated_tool(ctx)

    tools = await _tools(async_client)

    assert all(MCP_NAME.match(name) for name in tools)
    assert tools["function_time_now"]["_meta"]["ai.soit/tool_ref"] == "tool:function:time_now"
    assert tools["function_random_int"]["inputSchema"]["required"] == ["min", "max"]
    assert tools["function_gated_random"]["description"].endswith("Needs approval in SOIT before it runs.")


async def test_a_call_is_a_governed_run(async_client, async_db) -> None:
    response = await _rpc(
        async_client, "tools/call", {"name": "function_random_int", "arguments": {"min": 4, "max": 4}}
    )

    result = response.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == {"value": 4}
    assert result["content"] == [{"type": "text", "text": '{"value": 4}'}]
    run = await async_db.get(Run, result["_meta"]["ai.soit/run_id"])
    assert (run.mode, run.status) == ("tool", "succeeded")


async def test_arguments_the_tool_refuses_come_back_as_a_tool_error(async_client) -> None:
    response = await _rpc(async_client, "tools/call", {"name": "function_random_int", "arguments": {"min": 1}})

    result = response.json()["result"]
    assert result["isError"] is True
    assert "'max' is a required property" in result["content"][0]["text"]


async def test_a_limited_key_lists_and_calls_only_its_tools(async_client, ctx) -> None:
    _as(dataclasses.replace(ctx, api_key_id="key_1", allowed_tools=frozenset({"tool:function:time_now"})))

    tools = await _tools(async_client)
    refused = await _rpc(async_client, "tools/call", {"name": "function_random_int", "arguments": {}})

    assert list(tools) == ["function_time_now"]
    assert refused.json()["error"]["code"] == -32602


async def test_a_read_only_credential_is_offered_nothing(async_client, ctx) -> None:
    _as(dataclasses.replace(ctx, api_key_id="key_1", scopes=frozenset({"read"})))

    tools = await _tools(async_client)
    refused = await _rpc(async_client, "tools/call", {"name": "function_time_now", "arguments": {}})

    assert tools == {}
    assert refused.json()["error"]["code"] == -32602


async def test_a_gated_call_runs_when_called_again_after_approval(async_client, ctx) -> None:
    _register_gated_tool(ctx)
    call = {"name": "function_gated_random", "arguments": {"min": 9, "max": 9}}

    waiting = (await _rpc(async_client, "tools/call", call)).json()["result"]
    again = (await _rpc(async_client, "tools/call", call)).json()["result"]

    assert waiting["isError"] is True
    assert "needs approval" in waiting["content"][0]["text"]
    approval_id = waiting["_meta"]["ai.soit/approval_id"]
    assert again["_meta"]["ai.soit/approval_id"] == approval_id, "the same call waits on the same approval"

    resolved = await async_client.post(
        f"/api/v1/observe/approvals/{approval_id}/resolve", json={"status": "approved"}
    )
    assert resolved.status_code == 200
    done = (await _rpc(async_client, "tools/call", call)).json()["result"]

    assert (done["isError"], done["structuredContent"]) == (False, {"value": 9})
    assert done["_meta"]["ai.soit/run_id"] == waiting["_meta"]["ai.soit/run_id"]
    fresh = (await _rpc(async_client, "tools/call", call)).json()["result"]
    assert fresh["isError"] is True, "a finished call is not a standing approval"
    assert fresh["_meta"]["ai.soit/approval_id"] != approval_id


async def test_a_rejected_call_says_so(async_client, ctx) -> None:
    _register_gated_tool(ctx)
    call = {"name": "function_gated_random", "arguments": {"min": 9, "max": 9}}
    waiting = (await _rpc(async_client, "tools/call", call)).json()["result"]
    await async_client.post(
        f"/api/v1/observe/approvals/{waiting['_meta']['ai.soit/approval_id']}/resolve",
        json={"status": "rejected"},
    )

    rejected = (await _rpc(async_client, "tools/call", call)).json()["result"]

    assert rejected["isError"] is True
    assert "rejected" in rejected["content"][0]["text"]


async def test_protocol_errors(async_client) -> None:
    unknown_method = await _rpc(async_client, "resources/list")
    unknown_tool = await _rpc(async_client, "tools/call", {"name": "no_such_tool", "arguments": {}})
    not_json = await async_client.post("/mcp", content=b"{not json", headers={"content-type": "application/json"})
    batch = await async_client.post("/mcp", json=[{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
    not_rpc = await async_client.post("/mcp", json={"id": 1, "method": "ping"})
    old_version = await _rpc(async_client, "ping", **{"MCP-Protocol-Version": "1999-01-01"})
    ping = await _rpc(async_client, "ping", **{"MCP-Protocol-Version": "2025-06-18"})

    assert unknown_method.json()["error"]["code"] == -32601
    assert unknown_tool.json()["error"]["code"] == -32602
    assert (not_json.status_code, not_json.json()["error"]["code"]) == (400, -32700)
    assert (batch.status_code, batch.json()["error"]["code"]) == (400, -32600)
    assert not_rpc.status_code == 400
    assert old_version.status_code == 400
    assert ping.json() == {"jsonrpc": "2.0", "id": 7, "result": {}}


async def test_there_is_no_stream_and_no_session_to_end(async_client) -> None:
    for method in ("GET", "DELETE"):
        response = await async_client.request(method, "/mcp")
        assert response.status_code == 405
        assert response.headers["allow"] == "POST"


async def test_a_request_without_a_credential_is_challenged(async_client) -> None:
    _as(None)

    anonymous = await _rpc(async_client, "tools/list")
    bad_key = await _rpc(async_client, "tools/list", Authorization="Bearer sk_wrong")

    assert anonymous.status_code == 401
    assert anonymous.headers["www-authenticate"] == (
        'Bearer resource_metadata="http://testserver/.well-known/oauth-protected-resource/mcp"'
    )
    assert bad_key.headers["www-authenticate"].startswith('Bearer error="invalid_token", resource_metadata=')


async def test_without_any_credential_the_real_resolver_challenges_too(async_client) -> None:
    app.dependency_overrides.pop(mcp_caller, None)

    response = await _rpc(async_client, "tools/list")

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]


async def test_the_protected_resource_metadata_describes_the_endpoint(async_client, monkeypatch) -> None:
    plain = await async_client.get("/.well-known/oauth-protected-resource/mcp")
    monkeypatch.setattr(settings, "mcp_resource_url", "https://soit.example.com/mcp")
    monkeypatch.setattr(settings, "mcp_authorization_servers", ["https://login.example.com"])
    configured = await async_client.get("/.well-known/oauth-protected-resource")

    assert plain.json() == {
        "resource": "http://testserver/mcp",
        "bearer_methods_supported": ["header"],
        "resource_name": "SOIT MCP",
    }
    assert configured.json()["resource"] == "https://soit.example.com/mcp"
    assert configured.json()["authorization_servers"] == ["https://login.example.com"]


async def test_a_browser_on_another_origin_is_refused(async_client, monkeypatch) -> None:
    foreign = await _rpc(async_client, "ping", Origin="https://attacker.example")
    same = await _rpc(async_client, "ping", Origin="http://testserver")
    monkeypatch.setattr(settings, "mcp_allowed_origins", ["https://inspector.example"])
    listed = await _rpc(async_client, "ping", Origin="https://inspector.example")

    assert foreign.status_code == 403
    assert same.status_code == 200
    assert listed.status_code == 200
