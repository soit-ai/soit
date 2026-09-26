"""Billing API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreditBalanceResponse(BaseModel):
    """Current workspace credit balance derived from the ledger."""

    balance: Decimal
    granted_total: Decimal
    deducted_total: Decimal
    entry_count: int
    status: str = "ok"
    """ok, low (below warning threshold), or exhausted (enforcement blocks spend)."""
    enforcement_enabled: bool = False
    low_balance_threshold: Decimal = Decimal("0")


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

def _valid_thresholds(value: list[int]) -> list[int]:
    thresholds = sorted(set(value))
    if not thresholds or thresholds[0] < 1 or thresholds[-1] > 100:
        raise ValueError("Thresholds are percentages between 1 and 100")
    return thresholds


class BudgetCreate(BaseModel):
    """A spending limit for part of the workspace."""

    name: str = Field(min_length=1, max_length=255)
    scope_kind: Literal["workspace", "api_key", "user", "agent"] = "workspace"
    scope_id: str | None = Field(
        default=None, description="The key, user, service principal or agent id"
    )
    period: Literal["day", "month"] = "month"
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    thresholds: list[int] = Field(default_factory=lambda: [50, 80, 100], max_length=5)
    hard_stop: bool = True

    @field_validator("thresholds")
    @classmethod
    def _thresholds(cls, value: list[int]) -> list[int]:
        return _valid_thresholds(value)


class BudgetUpdate(BaseModel):
    """A change to a budget; its scope, period and currency are fixed."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    thresholds: list[int] | None = Field(default=None, max_length=5)
    hard_stop: bool | None = None
    status: Literal["active", "disabled"] | None = None

    @field_validator("thresholds")
    @classmethod
    def _thresholds(cls, value: list[int] | None) -> list[int] | None:
        return None if value is None else _valid_thresholds(value)


class BudgetResponse(BaseModel):
    id: str
    name: str
    scope_kind: str
    scope_id: str | None = None
    period: str
    amount: Decimal
    currency: str
    thresholds: list[int] = Field(default_factory=list, validation_alias="thresholds_json")
    hard_stop: bool
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetStatusResponse(BaseModel):
    budget: BudgetResponse
    period_start: datetime
    resets_at: datetime
    spent: Decimal
    remaining: Decimal
    percent: Decimal
    forecast: Decimal
    """Spend projected to the end of the period at the rate so far."""
