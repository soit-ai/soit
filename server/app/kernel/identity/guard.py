""" guard

RBAC decorators for service-layer authorization.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    require_resource_create_async,
    require_resource_delete_async,
    require_resource_read_async,
    require_resource_run_async,
    require_resource_update_async,
    require_resource_write_async,
)
from app.kernel.identity.rbac import (
    require_tenant_admin_async,
    require_workspace_owner_async,
    require_workspace_read_async,
    require_workspace_write_async,
)


def _resolve_ctx(bound_args: inspect.BoundArguments) -> RequestContext:
    """Resolve RequestContext from args or self."""
    ctx = bound_args.arguments.get("ctx")
    if ctx:
        return ctx
    self_obj = bound_args.arguments.get("self")
    if self_obj and hasattr(self_obj, "ctx"):
        return self_obj.ctx
    raise ValueError("RequestContext not available for RBAC guard")


def _resolve_value(
    bound_args: inspect.BoundArguments,
    arg_name: str | None,
    resolver: Callable[..., Any] | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    """Resolve a value from args or a resolver."""
    if resolver:
        return resolver(*args, **kwargs)
    if arg_name:
        return bound_args.arguments.get(arg_name)
    return None


def rbac_guard(
    resource_type: str,
    action: str,
    *,
    resource_id_arg: str | None = None,
    resource_id_resolver: Callable[..., Any] | None = None,
    owner_id_arg: str | None = None,
    owner_id_resolver: Callable[..., Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for resource-level RBAC checks."""
    action_key = action.strip().lower()
    if action_key not in ("read", "write", "delete", "create", "update", "run"):
        raise ValueError(f"Unsupported RBAC action: {action}")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(func)

        if not inspect.iscoroutinefunction(func) and not inspect.isasyncgenfunction(func):
            raise ValueError("rbac_guard requires async functions")

        if inspect.isasyncgenfunction(func):
            @wraps(func)
            async def async_gen_wrapper(*args, **kwargs):
                bound = signature.bind_partial(*args, **kwargs)
                ctx = _resolve_ctx(bound)
                resource_id = _resolve_value(
                    bound,
                    resource_id_arg,
                    resource_id_resolver,
                    args,
                    kwargs,
                )
                if not resource_id:
                    raise ValueError(f"RBAC guard requires resource id for {resource_type}")
                owner_id = _resolve_value(
                    bound,
                    owner_id_arg,
                    owner_id_resolver,
                    args,
                    kwargs,
                )
                await _apply_resource_guard_async(ctx, resource_type, action_key, str(resource_id), owner_id)
                async for item in func(*args, **kwargs):
                    yield item

            return async_gen_wrapper

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            bound = signature.bind_partial(*args, **kwargs)
            ctx = _resolve_ctx(bound)
            resource_id = _resolve_value(
                bound,
                resource_id_arg,
                resource_id_resolver,
                args,
                kwargs,
            )
            if not resource_id:
                raise ValueError(f"RBAC guard requires resource id for {resource_type}")
            owner_id = _resolve_value(
                bound,
                owner_id_arg,
                owner_id_resolver,
                args,
                kwargs,
            )
            await _apply_resource_guard_async(ctx, resource_type, action_key, str(resource_id), owner_id)
            return await func(*args, **kwargs)

        return async_wrapper

    return decorator


async def _apply_resource_guard_async(
    ctx: RequestContext,
    resource_type: str,
    action: str,
    resource_id: str,
    owner_id: str | None,
) -> None:
    """Apply resource permission check asynchronously."""
    if action == "read":
        await require_resource_read_async(ctx, resource_type, resource_id, owner_id)
        return
    if action == "write":
        await require_resource_write_async(ctx, resource_type, resource_id, owner_id)
        return
    if action == "delete":
        await require_resource_delete_async(ctx, resource_type, resource_id, owner_id)
        return
    if action == "create":
        await require_resource_create_async(ctx, resource_type, resource_id, owner_id)
        return
    if action == "update":
        await require_resource_update_async(ctx, resource_type, resource_id, owner_id)
        return
    if action == "run":
        await require_resource_run_async(ctx, resource_type, resource_id, owner_id)
        return
    raise ValueError(f"Unsupported RBAC action: {action}")


def workspace_guard(action: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for workspace or tenant-level RBAC checks."""
    action_key = action.strip().lower()
    if action_key not in ("read", "write", "owner", "admin"):
        raise ValueError(f"Unsupported workspace action: {action}")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(func)

        if not inspect.iscoroutinefunction(func):
            raise ValueError("workspace_guard requires async functions")

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            bound = signature.bind_partial(*args, **kwargs)
            ctx = _resolve_ctx(bound)
            await _apply_workspace_guard_async(ctx, action_key)
            return await func(*args, **kwargs)

        return async_wrapper

    return decorator


async def _apply_workspace_guard_async(ctx: RequestContext, action: str) -> None:
    """Apply workspace permission check (async)."""
    if action == "read":
        await require_workspace_read_async(ctx)
        return
    if action == "write":
        await require_workspace_write_async(ctx)
        return
    if action == "owner":
        await require_workspace_owner_async(ctx)
        return
    if action == "admin":
        await require_tenant_admin_async(ctx)
        return
    raise ValueError(f"Unsupported workspace action: {action}")
