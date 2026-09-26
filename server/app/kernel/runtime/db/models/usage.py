"""Daily usage aggregates: metered usage summed per day and dimension."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Index, Numeric, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class UsageDailyAggregate(SQLModel, table=True):
    """What one workspace used on one UTC day, per source, caller, key and model.

    Kept current by the ``cost.recorded`` consumer and rebuilt from the cost
    ledger by the nightly reconciler, so budgets and dashboards read a few rows
    instead of scanning every usage fact. Dimension columns are never null (an
    absent value is the empty string), which keeps the unique key exact.
    """

    __tablename__ = "usage_daily_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "day",
            "source",
            "user_id",
            "api_key_id",
            "provider_slug",
            "model_ref",
            "operation",
            "currency",
            name="uq_usage_daily_aggregates_dimensions",
        ),
        Index("ix_usage_daily_aggregates_scope_day", "tenant_id", "workspace_id", "day"),
    )

    id: str = Field(primary_key=True, default_factory=lambda: f"uda_{generate_ulid()}")
    tenant_id: str
    workspace_id: str
    day: date = Field(sa_column=Column(Date, nullable=False))

    source: str = ""
    """platform, gateway, or rehearsal for sandbox runs."""

    user_id: str = ""
    """The user or service principal the run belongs to."""

    api_key_id: str = ""
    provider_slug: str = ""
    model_ref: str = ""
    operation: str = ""
    currency: str = ""

    call_count: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    """Metered calls: one per usage fact."""

    prompt_tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    completion_tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    total_tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, default=0))
    amount: Decimal = Field(
        default=Decimal("0"), sa_column=Column(Numeric(18, 6), nullable=False, default=0)
    )
    """Priced amount in ``currency``; unpriced usage adds nothing."""

    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
