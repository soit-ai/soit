""" router

Direct tool calls: list the tools a caller may invoke and invoke one by
reference. Authentication is the same as the OpenAI-compatible ``/v1`` entry,
so an API key that calls models can call tools; ``allowed_tools`` on the key
narrows which. Each call is a run with ``mode="tool"``, named in the
``x-soit-run-id`` header, and goes through the governed tool gateway.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.session import get_async_db
from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.tools.catalog import CatalogTool
from app.kernel.runtime.tools.approval import tool_approval_rule
from app.kernel.runtime.tools.invocation import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    ToolInvocation,
)
from app.wiring.services import build_tool_invocation_service

router = APIRouter()

RUN_ID_HEADER = "x-soit-run-id"
IDEMPOTENCY_HEADER = "Idempotency-Key"


class ToolItemResponse(BaseModel):
    """One tool a caller may invoke."""

    ref: str
    name: str
    description: str
    input_schema: dict[str, Any]
    source_kind: str
    approval_required: bool
    risk_level: str


class ToolInvokeRequest(BaseModel):
    """The arguments of one call."""

    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(
        default=None,
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
        description="Same as the Idempotency-Key header; send one or the other",
    )


class ToolInvocationResponse(BaseModel):
    """The outcome of one call."""

    run_id: str
    tool_call_id: str
    tool_ref: str
    status: Literal["succeeded", "failed", "waiting_approval", "rejected"]
    idempotency_key: str
    result: Any = None
    error: str | None = None
    approval_id: str | None = None
    replayed: bool = False


def _item(tool: CatalogTool) -> ToolItemResponse:
    rule = tool_approval_rule(tool.policy)
    return ToolItemResponse(
        ref=tool.ref,
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        source_kind=tool.source_kind,
        approval_required=rule.required,
        risk_level=rule.risk_level,
    )


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def invocation_response(invocation: ToolInvocation) -> ToolInvocationResponse:
    """The API shape of an invocation outcome."""
    return ToolInvocationResponse(
        run_id=invocation.run_id,
        tool_call_id=invocation.tool_call_id,
        tool_ref=invocation.tool_ref,
        status=invocation.status,  # type: ignore[arg-type]
        idempotency_key=invocation.idempotency_key,
        result=_json_value(invocation.result),
        error=invocation.error,
        approval_id=invocation.approval_id,
        replayed=invocation.replayed,
    )


@router.get("", response_model=list[ToolItemResponse])
async def list_tools(
    ctx: Annotated[RequestContext, Depends(require_workspace_read_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[ToolItemResponse]:
    """Every tool of the workspace this caller may invoke, sorted by ref."""

    service = build_tool_invocation_service(db=db, ctx=ctx)
    return [_item(tool) for tool in await service.list_tools()]


@router.post(
    "/{tool_ref:path}/invoke",
    response_model=ToolInvocationResponse,
    responses={202: {"model": ToolInvocationResponse, "description": "Waiting for approval"}},
)
async def invoke_tool(
    tool_ref: str,
    payload: ToolInvokeRequest,
    response: Response,
    ctx: Annotated[RequestContext, Depends(require_workspace_write_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    idempotency_key: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> ToolInvocationResponse:
    """Invoke one tool; 202 when it waits for approval.

    Send the same call with the same Idempotency-Key to read its outcome
    again, or, once its approval is decided, to run it.
    """

    if idempotency_key and payload.idempotency_key and idempotency_key != payload.idempotency_key:
        raise ValidationError(
            "The Idempotency-Key header and idempotency_key differ",
            {"param": "idempotency_key"},
        )
    service = build_tool_invocation_service(db=db, ctx=ctx)
    invocation = await service.invoke(
        tool_ref,
        payload.arguments,
        idempotency_key=idempotency_key or payload.idempotency_key,
    )
    response.headers[RUN_ID_HEADER] = invocation.run_id
    response.headers[IDEMPOTENCY_HEADER] = invocation.idempotency_key
    if invocation.status == "waiting_approval":
        response.status_code = status.HTTP_202_ACCEPTED
    return invocation_response(invocation)


@router.get("/{tool_ref:path}", response_model=ToolItemResponse)
async def get_tool(
    tool_ref: str,
    ctx: Annotated[RequestContext, Depends(require_workspace_read_ctx)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> ToolItemResponse:
    """One tool, with the schema of its arguments."""

    service = build_tool_invocation_service(db=db, ctx=ctx)
    return _item(await service.get_tool(tool_ref))
