"""Workspace credit ledger.

Credits are a derived valuation: every deduction references the
run_cost_entries row it prices (``cost_entry_id`` is unique, so a retried
COST_RECORDED event can never double-book), and the measured usage itself
is never copied here. Balance is the signed sum of ``credits_delta``.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Index, Numeric
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class CreditLedgerEntry(SQLModel, table=True):
    """One signed credit movement for a workspace."""

    __tablename__ = "credit_ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'deduction' AND credits_delta <= 0)"
            " OR (kind = 'grant' AND credits_delta >= 0)"
            " OR kind = 'adjustment'",
            name="ck_credit_ledger_kind_sign",
        ),
        CheckConstraint(
            "kind <> 'deduction' OR cost_entry_id IS NOT NULL",
            name="ck_credit_ledger_deduction_has_cost_entry",
        ),
        Index(
            "uq_credit_ledger_cost_entry",
            "cost_entry_id",
            unique=True,
        ),
        Index(
            "ix_credit_ledger_scope_created",
            "tenant_id",
            "workspace_id",
            "created_at",
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Ledger entry ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    kind: str = Field()
    """Movement kind: grant, deduction, or adjustment."""

    credits_delta: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    """Signed credit movement; balance is the sum of this column."""

    cost_entry_id: str | None = Field(default=None, nullable=True)
    """run_cost_entries row this deduction prices; unique for idempotency."""

    run_id: str | None = Field(default=None, index=True)
    """Run the priced usage belongs to, when applicable."""

    currency: str | None = Field(default=None, nullable=True)
    """Source currency of the priced usage for deductions."""

    amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
    """Source monetary amount converted into credits."""

    conversion_snapshot_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    """Immutable conversion evidence: rate, source event, calculation."""

    note: str | None = Field(default=None, nullable=True)
    """Human-readable reason for grants and adjustments."""

    created_by: str = Field()
    """Actor: a user id for grants, system:credit-deduction for deductions."""

    created_at: datetime = Field(default_factory=utc_now, index=True)
    """Creation timestamp."""
