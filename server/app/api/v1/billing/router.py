"""Billing API routes: workspace credit balance, ledger, and grants."""

from fastapi import APIRouter, Depends

from app.api.v1.billing.dependencies import get_budget_service, get_credit_service
from app.api.v1.permissions import (
    require_workspace_governance_ctx,
    require_workspace_owner_ctx,
    require_workspace_read_ctx,
)
from app.kernel.contracts.context import RequestContext
from app.modules.billing.application.budgets import BudgetService, BudgetStatus
from app.modules.billing.application.schemas import (
    BudgetCreate,
    BudgetResponse,
    BudgetStatusResponse,
    BudgetUpdate,
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
    return await service.get_balance()


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
    return await service.list_entries(kind=kind, run_id=run_id, limit=limit, offset=offset)


@router.post("/credits/grants", response_model=CreditLedgerEntryResponse, status_code=201)
async def grant_credits(
    body: CreditGrantRequest,
    ctx: RequestContext = Depends(require_workspace_owner_ctx),
    service: CreditService = Depends(get_credit_service),
):
    """Grant credits to the current workspace (workspace owner only)."""
    _ = ctx
    return await service.grant(credits=body.credits, note=body.note)

def _status_response(status: BudgetStatus) -> BudgetStatusResponse:
    return BudgetStatusResponse(
        budget=BudgetResponse.model_validate(status.budget),
        period_start=status.period.starts_at,
        resets_at=status.period.resets_at,
        spent=status.spent,
        remaining=status.remaining,
        percent=status.percent,
        forecast=status.forecast,
    )


@router.get("/budgets", response_model=list[BudgetResponse])
async def list_budgets(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BudgetService = Depends(get_budget_service),
):
    """The workspace's budgets."""
    _ = ctx
    return [BudgetResponse.model_validate(budget) for budget in await service.list_budgets()]


@router.post("/budgets", response_model=BudgetResponse, status_code=201)
async def create_budget(
    body: BudgetCreate,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: BudgetService = Depends(get_budget_service),
):
    """Create a budget (workspace owner or admin)."""
    _ = ctx
    return BudgetResponse.model_validate(await service.create_budget(body))


@router.get("/budgets/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BudgetService = Depends(get_budget_service),
):
    _ = ctx
    return BudgetResponse.model_validate(await service.get_budget(budget_id))


@router.patch("/budgets/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str,
    body: BudgetUpdate,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: BudgetService = Depends(get_budget_service),
):
    _ = ctx
    return BudgetResponse.model_validate(await service.update_budget(budget_id, body))


@router.delete("/budgets/{budget_id}", status_code=204)
async def delete_budget(
    budget_id: str,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: BudgetService = Depends(get_budget_service),
):
    _ = ctx
    await service.delete_budget(budget_id)


@router.get("/budgets/{budget_id}/status", response_model=BudgetStatusResponse)
async def get_budget_status(
    budget_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BudgetService = Depends(get_budget_service),
):
    """Spend in the current period, what remains, and a forecast to its end."""
    _ = ctx
    return _status_response(await service.status(budget_id))
