"""Regression tests for application egress paths outside the crawler."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.adapters.http.governed_client import governed_httpx_client
from app.adapters.llm.router import LLMRouterPort, RuntimeProviderConfig
from app.adapters.plugins.http_runtime import HTTPPluginRuntimePort
from app.adapters.tools.mcp import MCPToolAdapter
from app.kernel.commons.errors import ForbiddenError
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.security import egress
from app.modules.modelhub.infra.providers import ProviderCatalogAdapter
from app.modules.notification.domain.models import (
    Notification,
    NotificationDelivery,
    NotificationEndpoint,
)
from app.modules.notification.handlers.apprise_delivery import (
    handle_notification_delivery_outbox,
)
from app.modules.plugin.domain.models import PluginInstalledArtifact
from app.modules.secrets.domain.models import Secret
from app.settings.settings import settings


class PrivateResolver:
    async def resolve(self, hostname: str, port: int) -> list[str]:
        return ["169.254.169.254"]


class PublicResolver:
    async def resolve(self, hostname: str, port: int) -> list[str]:
        return ["93.184.216.34"]


class HostAddressResolver:
    async def resolve(self, hostname: str, port: int) -> list[str]:
        if hostname == "public.example.com":
            return ["93.184.216.34"]
        return ["169.254.169.254"]


def _configure_allowlist(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", [host])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)


def _private_guard() -> egress.GovernedEgressGuard:
    return egress.GovernedEgressGuard(address_resolver=PrivateResolver())


@pytest.mark.asyncio
async def test_governed_httpx_client_rechecks_redirect_destination(
    ctx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(
        settings,
        "egress_allowlist",
        ["public.example.com", "metadata.example.com"],
    )
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "public.example.com":
            return httpx.Response(
                302,
                headers={"location": "https://metadata.example.com/latest/meta-data"},
            )
        raise AssertionError("Redirect target must be blocked before transport")

    client = governed_httpx_client(
        ctx=ctx,
        resource_ref="plugin:redirect-test",
        egress_guard=egress.GovernedEgressGuard(
            address_resolver=HostAddressResolver()
        ),
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )
    try:
        with pytest.raises(ForbiddenError, match="non-public"):
            await client.get("https://public.example.com/start")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_tool_egress_check_does_not_depend_on_tool_name(
    ctx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_allowlist(monkeypatch, "allowed.example.com")

    class RecordingGateway:
        def __init__(self) -> None:
            self.called = False

        async def invoke(self, tool_ref, parameters, **kwargs):
            self.called = True
            return ToolResponse(result={"ok": True}, success=True)

    gateway = RecordingGateway()
    policy = ToolPolicyGateway(gateway=gateway, ctx=ctx)

    with pytest.raises(ForbiddenError):
        await policy.invoke(
            "tool:function:not_an_http_name",
            {"payload": {"callback": "http://169.254.169.254/latest/meta-data"}},
        )

    assert gateway.called is False


@pytest.mark.asyncio
async def test_mcp_private_endpoint_is_rejected_before_session(
    db,
    ctx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_allowlist(monkeypatch, "mcp.example.com")
    db.add(
        PluginInstalledArtifact(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            plugin_id="plg_guarded_mcp",
            plugin_version_id="plv_guarded_mcp",
            installation_id="pli_guarded_mcp",
            artifact_kind="mcp_server",
            artifact_ref="mcp_server:guarded",
            artifact_id="mcp_server:guarded",
            enabled=True,
            state="enabled",
            metadata_json={
                "mcp_server": {
                    "name": "guarded",
                    "endpoint": "https://mcp.example.com/mcp",
                    "transport": "streamable_http",
                    "auth_config": {},
                }
            },
        )
    )
    db.commit()
    called = False

    @asynccontextmanager
    async def session_factory(**_kwargs):
        nonlocal called
        called = True
        yield SimpleNamespace()

    response = await MCPToolAdapter(
        session_factory=session_factory,
        egress_guard=_private_guard(),
    ).invoke("mcp_tool:guarded:echo", {}, db=db, ctx=ctx)

    assert response.success is False
    assert "non-public" in (response.error or "")
    assert called is False


@pytest.mark.asyncio
async def test_plugin_private_runtime_is_rejected_before_http(
    ctx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_allowlist(monkeypatch, "plugin.example.com")

    class Registry:
        def get(self, **kwargs):
            return (
                "1.0.0",
                {
                    "manifest": {
                        "runtime": {
                            "type": "http",
                            "base_url": "https://plugin.example.com",
                        }
                    }
                },
            )

    adapter = HTTPPluginRuntimePort(
        registry=Registry(),
        egress_guard=_private_guard(),
    )

    with pytest.raises(ForbiddenError, match="non-public"):
        await adapter.invoke(
            plugin_name="guarded",
            version="1.0.0",
            tool_name="echo",
            input_json={},
            ctx=ctx,
        )


@pytest.mark.asyncio
async def test_modelhub_private_base_url_is_rejected_before_sdk(
    ctx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_allowlist(monkeypatch, "models.example.com")
    sdk = AsyncMock()
    monkeypatch.setattr("app.modules.modelhub.infra.providers.AsyncOpenAI", sdk)
    adapter = ProviderCatalogAdapter(egress_guard=_private_guard())

    with pytest.raises(ForbiddenError, match="non-public"):
        await adapter.list_models(
            ctx=ctx,
            provider_kind="openai_compatible",
            api_key="test-key",
            base_url="https://models.example.com/v1",
        )

    sdk.assert_not_called()


@pytest.mark.asyncio
async def test_runtime_model_provider_private_base_url_is_rejected_before_factory(
    ctx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_allowlist(monkeypatch, "runtime-models.example.com")
    native_factory = AsyncMock()
    router = LLMRouterPort(
        providers={},
        provider_resolver=lambda request_ctx, slug, model_id: RuntimeProviderConfig(
            slug=slug,
            kind="openai_compatible",
            adapter_backend="native",
            status="active",
            base_url="https://runtime-models.example.com/v1",
            provider_capabilities={"chat": True},
            capability_matrix={"chat": {"merged": True}},
        ),
        native_factory=native_factory,
        egress_guard=_private_guard(),
    )

    with pytest.raises(ForbiddenError, match="non-public"):
        await router.resolve_route("model:custom:test", ctx, ("chat",))

    native_factory.assert_not_called()


@pytest.mark.asyncio
async def test_notification_private_target_is_rejected_before_sender(
    db,
    ctx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_allowlist(monkeypatch, "hooks.example.com")
    notification = Notification(
        id="ntf_guarded",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        type="system",
        title="Guarded",
        content="Body",
    )
    secret = Secret(
        id="sec_notification_guarded",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="Guarded endpoint",
        secret_ref="secret:sec_notification_guarded",
    )
    endpoint = NotificationEndpoint(
        id="nep_guarded",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        name="Guarded endpoint",
        kind="webhook",
        secret_id=secret.id,
        display_target="json://hooks.example.com/***",
    )
    delivery = NotificationDelivery(
        id="ndel_guarded",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        notification_id=notification.id,
        endpoint_id=endpoint.id,
    )
    db.add_all([notification, secret, endpoint, delivery])
    db.commit()
    secrets = SimpleNamespace(
        get_secret=AsyncMock(return_value="json://hooks.example.com/notify")
    )
    sender = AsyncMock(return_value=True)

    with pytest.raises(RuntimeError, match="notification delivery failed"):
        await handle_notification_delivery_outbox(
            db,
            SimpleNamespace(payload_json={"delivery_id": delivery.id}),
            secrets_port=secrets,
            sender=sender,
            egress_guard=_private_guard(),
        )

    sender.assert_not_awaited()
