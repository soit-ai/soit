"""Billing API routes: workspace credit balance, ledger, and grants."""

from fastapi import APIRouter, Depends

from app.api.v1.billing.dependencies import get_credit_service
from app.api.v1.permissions import (
    require_workspace_owner_ctx,
    require_workspace_read_ctx,
)
from app.kernel.contracts.context import RequestContext
from app.modules.billing.application.schemas import (
    CreditBalanceResponse,
    CreditGrantRequest,
    CreditLedgerEntryResponse,
)
from app.modules.billing.application.service import CreditService

router = APIRouter()


@router.get("/credits/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: CreditService = Depends(get_credit_service),
):
    """Current workspace credit balance derived from the ledger."""
    _ = ctx
    return service.get_balance()


@router.get("/credits/entries", response_model=list[CreditLedgerEntryResponse])
async def list_credit_entries(
    kind: str | None = None,
    run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: CreditService = Depends(get_credit_service),
):
    """List signed credit movements, newest first."""
    _ = ctx
    return service.list_entries(kind=kind, run_id=run_id, limit=limit, offset=offset)


@router.post("/credits/grants", response_model=CreditLedgerEntryResponse, status_code=201)
async def grant_credits(
    body: CreditGrantRequest,
    ctx: RequestContext = Depends(require_workspace_owner_ctx),
    service: CreditService = Depends(get_credit_service),
):
    """Grant credits to the current workspace (workspace owner only)."""
    _ = ctx
    return service.grant(credits=body.credits, note=body.note)
