""" router

Registry-backed ToolPort implementation.

Behaviour
- If a tool_ref exists in the runtime registry (kind="tool"), resolve its tool_spec and execute via adapter.
- Otherwise, fall back to raw HTTPToolsPort behaviour (expects url/method/headers/body in parameters).

Supported adapters (initial)
- http: uses HTTPToolsPort
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.adapters.tools.function import FunctionToolsPort
from app.adapters.tools.http import HTTPToolsPort
from app.adapters.tools.mcp import MCPToolAdapter
from app.kernel.commons.errors import ForbiddenError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.registry.deps import get_registry
from app.kernel.security.egress import get_egress_policy
from app.kernel.specs.validator import validate_spec


class RegistryToolRouterPort(ToolPort):
    """ToolPort that resolves tool specs from the in-process registry."""

    def __init__(
        self,
        *,
        http_port: HTTPToolsPort | None = None,
        function_port: FunctionToolsPort | None = None,
        mcp_adapter: MCPToolAdapter | None = None,
        plugin_runtime_port: PluginRuntimePort | None = None,
        secrets_port_factory: Callable[[RequestContext], SecretsPort] | None = None,
    ):
        self.http_port = http_port or HTTPToolsPort()
        self.function_port = function_port or FunctionToolsPort()
        self.mcp_adapter = mcp_adapter or MCPToolAdapter()
        self.plugin_runtime_port = plugin_runtime_port
        self.secrets_port_factory = secrets_port_factory
        self._template_pattern = re.compile(r"\{\{\s*inputs\.([^\s{}]+)\s*\}\}")

    def _builtin_tool_spec(self, tool_ref: str) -> dict[str, Any] | None:
        """Return builtin tool spec for known refs."""
        if tool_ref == "tool:http:request":
            return {
                "name": "request",
                "adapter": "http",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "method": {"type": "string"},
                        "headers": {"type": "object"},
                        "query": {"type": "object"},
                        "body": {"type": "object"},
                    },
                    "required": ["url"],
                },
                "output_schema": {},
                "policy": {"audit_level": "basic"},
                "http": {
                    "method": "POST",
                    "url": "{{ inputs.url }}",
                },
            }
        if tool_ref == "tool:function:time_now":
            return {
                "name": "time_now",
                "adapter": "function",
                "input_schema": {"type": "object"},
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "iso": {"type": "string"},
                        "timestamp": {"type": "number"},
                    },
                    "required": ["iso", "timestamp"],
                },
                "policy": {"audit_level": "basic"},
                "function": {"entrypoint": "app.utils.builtin_tools:time_now"},
            }
        if tool_ref == "tool:function:random_int":
            return {
                "name": "random_int",
                "adapter": "function",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "integer"},
                        "max": {"type": "integer"},
                    },
                    "required": ["min", "max"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                },
                "policy": {"audit_level": "basic"},
                "function": {"entrypoint": "app.utils.builtin_tools:random_int"},
            }
        if tool_ref == "tool:function:knowledge_query":
            return {
                "name": "knowledge_query",
                "adapter": "function",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "knowledge_id": {"type": "string"},
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 100},
                        "index_id": {"type": ["string", "null"]},
                        "filter": {"type": ["object", "null"]},
                        "include_snippets": {"type": "boolean"},
                        "strategy": {"type": ["string", "null"]},
                    },
                    "required": ["knowledge_id", "query"],
                },
                "output_schema": {"type": "object"},
                "policy": {"audit_level": "basic"},
                "function": {"entrypoint": "app.modules.knowledge.runtime.tool_entrypoint:knowledge_query"},
            }
        if tool_ref == "builtin.ticket.create_review_ticket":
            return {
                "name": "create_review_ticket",
                "adapter": "function",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "customer_id": {"type": "string"},
                        "priority": {"type": "string"},
                        "message": {"type": "string"},
                        "classification": {"type": "string"},
                        "api_token": {"type": "string"},
                    },
                    "required": ["customer_id", "message"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "status": {"type": "string"},
                        "review_url": {"type": "string"},
                    },
                    "required": ["ticket_id", "status", "review_url"],
                },
                "policy": {
                    "audit_level": "full",
                    "secret_refs": ["secret:ticket_api_key"],
                    "egress": {"allow": ["tickets.example.local"]},
                },
                "function": {"entrypoint": "app.utils.demo_ticket_tools:create_review_ticket"},
            }
        return None

    def register_builtin(self, tool_ref: str, ctx: RequestContext) -> bool:
        """Register builtin tool spec into registry for current scope."""
        tool_spec = self._builtin_tool_spec(tool_ref)
        if not tool_spec:
            return False
        reg = get_registry()
        reg.register(
            kind="tool",
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            name=tool_ref,
            version="1.0.0",
            payload={"tool_spec": tool_spec},
        )
        return True

    def _register_builtin(self, tool_ref: str, ctx: RequestContext) -> bool:
        """Backward-compatible alias for older adapter callers."""
        return self.register_builtin(tool_ref, ctx)

    async def _resolve_api_key(
        self,
        ctx: RequestContext,
        auth_cfg: dict[str, Any],
    ) -> str | None:
        """Resolve api key secret if configured."""
        api_key_cfg = auth_cfg.get("api_key") or {}
        secret_ref = api_key_cfg.get("secret_ref")
        if not secret_ref:
            return None
        if not self.secrets_port_factory:
            raise ValidationError("Secrets port factory not configured")
        secrets_port = self.secrets_port_factory(ctx)
        return await secrets_port.get_secret(secret_ref=secret_ref)

    def _resolve_input_path(self, inputs: dict[str, Any], path: str) -> Any:
        """Resolve nested input value by dot path."""
        current: Any = inputs
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    def _render_template(self, value: Any, inputs: dict[str, Any]) -> Any:
        """Render template strings using inputs."""
        if isinstance(value, str):
            matches = list(self._template_pattern.finditer(value))
            if not matches:
                return value
            rendered = value
            for match in matches:
                token = match.group(0)
                path = match.group(1)
                resolved = self._resolve_input_path(inputs, path)
                if resolved is None:
                    raise ValidationError(f"Missing tool input for template: inputs.{path}")
                if value.strip() == token and not isinstance(resolved, str):
                    return resolved
                rendered = rendered.replace(token, str(resolved))
            return rendered
        if isinstance(value, dict):
            return {k: self._render_template(v, inputs) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_template(v, inputs) for v in value]
        return value

    def _validate_inputs(self, tool_ref: str, tool_spec: dict[str, Any], inputs: dict[str, Any]) -> None:
        """Validate tool inputs against input_schema."""
        input_schema = tool_spec.get("input_schema")
        if input_schema is None:
            raise ValidationError(f"Tool '{tool_ref}' missing input_schema")
        validate_spec(inputs, input_schema)

    def _validate_output(self, tool_ref: str, tool_spec: dict[str, Any], output: Any) -> None:
        """Validate tool output against output_schema."""
        output_schema = tool_spec.get("output_schema")
        if output_schema is None:
            return
        validate_spec(output, output_schema)

    def _resolve_http_url(
        self,
        tool_spec: dict[str, Any],
        tool_inputs: dict[str, Any],
        parameters: dict[str, Any],
    ) -> str | None:
        http_cfg = tool_spec.get("http") or {}
        url = self._render_template(http_cfg.get("url"), tool_inputs) if http_cfg.get("url") else None
        if not url:
            url = parameters.get("url")
        base_url = http_cfg.get("base_url")
        path = http_cfg.get("path")
        if not url and base_url and path:
            url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        return url

    def _enforce_tool_egress(
        self,
        ctx: RequestContext,
        url: str | None,
        allowlist: list[Any] | None,
        tool_ref: str,
    ) -> None:
        """Enforce tool-level egress allowlist if provided."""
        if not url or not allowlist:
            return
        policy = get_egress_policy()
        is_allowed = policy.check_allowed(ctx=ctx, url=url, workspace_allowlist=allowlist)
        if not is_allowed:
            raise ForbiddenError(
                "Tool egress blocked by allowlist",
                {"tool_ref": tool_ref, "url": url},
            )

    async def _resolve_reserved_auth_payload(
        self,
        ctx: RequestContext,
        auth_cfg: dict[str, Any],
    ) -> dict[str, dict[str, str]]:
        """Resolve plugin runtime auth material into a reserved transport envelope."""
        auth_payload: dict[str, dict[str, str]] = {"headers": {}, "query": {}}
        if auth_cfg.get("type") != "api_key":
            return auth_payload
        api_key = await self._resolve_api_key(ctx, auth_cfg)
        api_key_cfg = auth_cfg.get("api_key") or {}
        key_in = api_key_cfg.get("in")
        key_name = api_key_cfg.get("name")
        if api_key and key_in == "header" and key_name:
            auth_payload["headers"][key_name] = api_key
        elif api_key and key_in == "query" and key_name:
            auth_payload["query"][key_name] = api_key
        return auth_payload

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        # Route mcp_tool:* refs directly to MCP adapter
        if tool_ref.startswith("mcp_tool:"):
            mcp_ctx = kwargs.get("ctx")
            if mcp_ctx is not None and self.secrets_port_factory and "secrets_port" not in kwargs:
                kwargs["secrets_port"] = self.secrets_port_factory(mcp_ctx)
            return await self.mcp_adapter.invoke(tool_ref, parameters, **kwargs)

        strict_registry: bool = bool(kwargs.get("strict_registry", False))
        ctx: RequestContext | None = kwargs.get("ctx")
        if ctx is None:
            # allow callers to pass tenant/workspace explicitly
            tenant_id = kwargs.get("tenant_id")
            workspace_id = kwargs.get("workspace_id")
            if tenant_id and workspace_id:
                ctx = RequestContext(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    user_id=str(kwargs.get("user_id") or "system"),
                )
            else:
                # No ctx: in strict mode we refuse to run unscoped tools
                if strict_registry:
                    raise ValidationError("Tool invocation requires ctx (tenant_id/workspace_id) in strict mode")
                return await self.http_port.invoke(tool_ref=tool_ref, parameters=parameters, **kwargs)

        reg = get_registry()
        found = reg.get_latest(kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name=tool_ref)
        if not found:
            if self._register_builtin(tool_ref, ctx):
                found = reg.get_latest(
                    kind="tool",
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    name=tool_ref,
                )
        if not found:
            # Not registered
            if strict_registry:
                raise ValidationError(f"Tool not registered for tenant/workspace: {tool_ref}")
            return await self.http_port.invoke(tool_ref=tool_ref, parameters=parameters, **kwargs)

        _, payload = found
        tool_spec = payload.get("tool_spec") or {}
        adapter = tool_spec.get("adapter")
        tool_inputs: dict[str, Any] = {}
        if adapter == "http":
            body = parameters.get("body")
            if isinstance(body, dict):
                tool_inputs.update(body)
            elif body is not None:
                tool_inputs["body"] = body
            extra_inputs = {
                k: v
                for k, v in parameters.items()
                if k not in ("url", "method", "headers", "body", "query")
            }
            tool_inputs.update(extra_inputs)
            for key in ("url", "method", "headers", "query"):
                if key in parameters:
                    tool_inputs[key] = parameters[key]
        else:
            if "body" in parameters:
                tool_inputs = parameters.get("body") or {}
            else:
                tool_inputs = {
                    k: v
                    for k, v in parameters.items()
                    if k not in ("url", "method", "headers", "body", "query")
                }

        self._validate_inputs(tool_ref, tool_spec, tool_inputs)
        if adapter == "function" and tool_ref == "tool:function:knowledge_query":
            tool_inputs = {
                **tool_inputs,
                "ctx": {
                    "tenant_id": ctx.tenant_id,
                    "workspace_id": ctx.workspace_id,
                    "user_id": ctx.user_id,
                },
            }
        plugin_info = (payload or {}).get("plugin") or {}
        if plugin_info:
            plugin_name = plugin_info.get("name")
            version = plugin_info.get("version")
            if not plugin_name or not version:
                raise ValidationError("Plugin metadata missing name/version")
            if not self.plugin_runtime_port:
                raise ValidationError("Plugin runtime port not configured")
            policy_cfg = tool_spec.get("policy") or {}
            egress_cfg = policy_cfg.get("egress") or {}
            allowlist = egress_cfg.get("allow") or []
            self._enforce_tool_egress(
                ctx,
                self._resolve_http_url(tool_spec, tool_inputs, parameters),
                allowlist,
                tool_ref,
            )
            auth_payload = await self._resolve_reserved_auth_payload(ctx, tool_spec.get("auth") or {})
            if auth_payload["headers"] or auth_payload["query"]:
                tool_inputs = {
                    **tool_inputs,
                    "_soit_auth": auth_payload,
                }
            tool_name = tool_ref.split(":")[-1] if ":" in tool_ref else tool_ref
            result = await self.plugin_runtime_port.invoke(
                plugin_name=plugin_name,
                version=version,
                tool_name=tool_name,
                input_json=tool_inputs,
                ctx=ctx,
                timeout_s=kwargs.get("timeout_s"),
            )
            self._validate_output(tool_ref, tool_spec, result)
            return ToolResponse(
                result=result,
                success=True,
                metadata={
                    "source_kind": "plugin",
                    "adapter": "plugin",
                    "plugin_name": plugin_name,
                    "plugin_version": version,
                    "tool_ref": tool_ref,
                },
            )
        if adapter == "http":
            http_cfg = tool_spec.get("http") or {}
            url = self._resolve_http_url(tool_spec, tool_inputs, parameters)
            if not url:
                raise ValidationError(f"HTTP tool '{tool_ref}' missing url (tool_spec.http.url)")
            method = parameters.get("method") or http_cfg.get("method") or "POST"
            headers = {}
            headers.update(self._render_template(http_cfg.get("headers") or {}, tool_inputs))
            headers.update(parameters.get("headers") or {})
            query = {}
            query.update(self._render_template(http_cfg.get("query") or {}, tool_inputs))
            query.update(parameters.get("query") or {})

            # default body: user parameters (excluding transport keys)
            if http_cfg.get("body_template") is not None:
                body = self._render_template(http_cfg.get("body_template"), tool_inputs)
            else:
                body = {
                    k: v
                    for k, v in tool_inputs.items()
                    if k not in ("url", "method", "headers", "query")
                }

            auth_cfg = tool_spec.get("auth") or {}
            if auth_cfg.get("type") == "api_key":
                api_key = await self._resolve_api_key(ctx, auth_cfg)
                api_key_cfg = auth_cfg.get("api_key") or {}
                key_in = api_key_cfg.get("in")
                key_name = api_key_cfg.get("name")
                if api_key and key_in == "header" and key_name:
                    headers[key_name] = api_key
                elif api_key and key_in == "query" and key_name:
                    query[key_name] = api_key

            policy_cfg = tool_spec.get("policy") or {}
            egress_cfg = policy_cfg.get("egress") or {}
            allowlist = egress_cfg.get("allow") or []
            self._enforce_tool_egress(ctx, url, allowlist, tool_ref)

            timeout_ms = policy_cfg.get("timeout_ms") or http_cfg.get("timeout_ms")
            timeout_s = timeout_ms / 1000 if timeout_ms else None
            http_params = {
                "url": url,
                "method": method,
                "headers": headers,
                "body": body,
                "query": query,
            }
            response = await self.http_port.invoke(
                tool_ref=tool_ref,
                parameters=http_params,
                timeout_s=timeout_s,
                **kwargs,
            )
            if response.success:
                self._validate_output(tool_ref, tool_spec, response.result)
            return response

        if adapter == "function":
            fn_cfg = tool_spec.get("function") or {}
            entrypoint = fn_cfg.get("entrypoint")
            if not entrypoint:
                raise ValidationError(f"Function tool '{tool_ref}' missing entrypoint")

            response = await self.function_port.invoke(
                tool_ref=tool_ref,
                parameters={
                    "entrypoint": entrypoint,
                    "inputs": tool_inputs,
                },
                **kwargs,
            )
            if response.success:
                self._validate_output(tool_ref, tool_spec, response.result)
            policy_cfg = tool_spec.get("policy") or {}
            metadata = {
                **(response.metadata or {}),
                "source_kind": "registry",
                "adapter": "function",
                "tool_ref": tool_ref,
            }
            if policy_cfg.get("secret_refs"):
                metadata["secret_refs"] = policy_cfg.get("secret_refs")
            if policy_cfg.get("egress"):
                metadata["egress_policy"] = policy_cfg.get("egress")
            return ToolResponse(
                result=response.result,
                success=response.success,
                error=response.error,
                metadata=metadata,
            )

        # adapter not supported yet
        raise ValidationError(f"Unsupported tool adapter: {adapter} (tool_ref={tool_ref})")
