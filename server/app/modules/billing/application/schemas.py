"""Billing API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreditBalanceResponse(BaseModel):
    """Current workspace credit balance derived from the ledger."""

    balance: Decimal
    granted_total: Decimal
    deducted_total: Decimal
    entry_count: int


class CreditLedgerEntryResponse(BaseModel):
    """One signed credit movement."""

    id: str
    tenant_id: str
    workspace_id: str
    kind: str
    credits_delta: Decimal
    cost_entry_id: str | None
    run_id: str | None
    currency: str | None
    amount: Decimal | None
    conversion_snapshot_json: dict[str, Any]
    note: str | None
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditGrantRequest(BaseModel):
    """Grant credits to the current workspace."""

    credits: Decimal = Field(gt=0)
    note: str | None = None
