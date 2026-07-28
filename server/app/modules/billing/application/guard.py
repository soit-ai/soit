"""Balance-based credit guard: warn when low, hard-stop when exhausted."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlmodel import Session

from app.kernel.commons.errors import CreditExhaustedError
from app.kernel.contracts.context import RequestContext
from app.modules.billing.domain.models import CreditLedgerEntry
from app.settings.settings import settings

logger = logging.getLogger(__name__)


class CreditBalanceGuard:
    """Blocks metered invocations for workspaces with an exhausted balance.

    Enforcement is opt-in via credit_enforcement_enabled so fresh installs
    (zero ledger, zero balance) keep working until credits are operated.
    """

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def _balance(self) -> Decimal:
        query = select(
            func.coalesce(func.sum(CreditLedgerEntry.credits_delta), 0)
        ).where(
            and_(
                CreditLedgerEntry.tenant_id == self.ctx.tenant_id,
                CreditLedgerEntry.workspace_id == self.ctx.workspace_id,
            )
        )
        row = self.db.exec(query).one()
        value = row if isinstance(row, int | float | Decimal) else row[0]
        return Decimal(str(value))

    async def check(self, *, operation: str) -> None:
        """Raise CreditExhaustedError when the workspace balance is spent."""
        if not settings.credit_enforcement_enabled:
            return
        balance = self._balance()
        if balance <= 0:
            raise CreditExhaustedError(
                details={
                    "operation": operation,
                    "balance": format(balance, "f"),
                    "tenant_id": self.ctx.tenant_id,
                    "workspace_id": self.ctx.workspace_id,
                }
            )
        threshold = Decimal(str(settings.credit_low_balance_threshold))
        if balance < threshold:
            logger.warning(
                "Workspace credit balance low: tenant=%s workspace=%s balance=%s threshold=%s operation=%s",
                self.ctx.tenant_id,
                self.ctx.workspace_id,
                format(balance, "f"),
                format(threshold, "f"),
                operation,
            )
