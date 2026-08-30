"""Security domain models.

Security audit persistence is unified under ``app.kernel.runtime.db.models.audit.AuditEvent``.
The one table owned here is the policy revision ledger: the audit event says a
policy changed, the revision says what it changed to and lets that state be
read back, compared and restored.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import JSON, Column, Field, Index, SQLModel, UniqueConstraint

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_policy_revision_id() -> str:
    """Generate policy revision ID."""
    return f"pr_{generate_ulid()}"


class PolicyRevision(SQLModel, table=True):
    """One saved state of a scope's governance policy.

    Rows are append-only. A rollback does not delete anything: it writes a new
    revision carrying the older content and naming what it restored, so the
    history stays a record of what was in force rather than of what somebody
    wishes had been.
    """

    __tablename__ = "policy_revisions"
    __table_args__ = (
        # Revision numbers are per scope, and two saves must not share one.
        UniqueConstraint(
            "tenant_id",
            "scope",
            "scope_id",
            "revision",
            name="uq_policy_revisions_scope_revision",
        ),
        Index("ix_policy_revisions_scope", "tenant_id", "scope", "scope_id", "revision"),
    )

    id: str = Field(default_factory=generate_policy_revision_id, primary_key=True)
    tenant_id: str = Field(index=True)

    scope: str = Field(description="tenant or workspace")
    scope_id: str = Field(
        description="The tenant or workspace the policy belongs to.",
    )
    workspace_id: str | None = Field(default=None, index=True)

    revision: int = Field(description="Monotonic per scope, starting at 1.")
    bundle_id: str = Field(
        index=True,
        description="Derived from the content, so identical policies share it.",
    )
    document_json: dict = Field(default_factory=dict, sa_column=Column(JSON))

    note: str | None = Field(default=None)
    restored_from_revision: int | None = Field(
        default=None,
        description="Set when this revision was written by a rollback.",
    )

    created_by: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
