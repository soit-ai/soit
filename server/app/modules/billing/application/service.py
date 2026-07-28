"""Workspace credit service: balance, ledger listing, grants."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlmodel import Session

from app.kernel.contracts.context import RequestContext
from app.modules.billing.application.schemas import (
    CreditBalanceResponse,
    CreditLedgerEntryResponse,
)
from app.modules.billing.domain.models import CreditLedgerEntry


class CreditService:
    """Workspace-scoped credit ledger queries and grants."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def _scope_clauses(self) -> list[Any]:
        return [
            CreditLedgerEntry.tenant_id == self.ctx.tenant_id,
            CreditLedgerEntry.workspace_id == self.ctx.workspace_id,
        ]

    def get_balance(self) -> CreditBalanceResponse:
        """Balance is the signed sum of the ledger; no cached counter to drift."""
        query = select(
            func.coalesce(func.sum(CreditLedgerEntry.credits_delta), 0),
            func.coalesce(
                func.sum(
                    case(
                        (CreditLedgerEntry.credits_delta > 0, CreditLedgerEntry.credits_delta),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (CreditLedgerEntry.credits_delta < 0, CreditLedgerEntry.credits_delta),
                        else_=0,
                    )
                ),
                0,
            ),
            func.count(CreditLedgerEntry.id),
        ).where(and_(*self._scope_clauses()))
        row = self.db.exec(query).one()
        return CreditBalanceResponse(
            balance=Decimal(str(row[0])),
            granted_total=Decimal(str(row[1])),
            deducted_total=Decimal(str(row[2])),
            entry_count=int(row[3]),
        )

    def list_entries(
        self,
        *,
        kind: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CreditLedgerEntryResponse]:
        clauses = self._scope_clauses()
        if kind:
            clauses.append(CreditLedgerEntry.kind == kind)
        if run_id:
            clauses.append(CreditLedgerEntry.run_id == run_id)
        query = (
            select(CreditLedgerEntry)
            .where(and_(*clauses))
            .order_by(CreditLedgerEntry.created_at.desc(), CreditLedgerEntry.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        entries = [row if hasattr(row, "id") else row[0] for row in rows]
        return [CreditLedgerEntryResponse.model_validate(entry) for entry in entries]

    def grant(self, *, credits: Decimal, note: str | None = None) -> CreditLedgerEntryResponse:
        if credits <= 0:
            raise ValueError("Grant credits must be positive")
        entry = CreditLedgerEntry(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            kind="grant",
            credits_delta=credits,
            note=note,
            created_by=self.ctx.user_id or "system:credit-grant",
            conversion_snapshot_json={},
        )
        self.db.add(entry)
        self.db.flush()
        self.db.refresh(entry)
        return CreditLedgerEntryResponse.model_validate(entry)
