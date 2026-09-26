"""Sealed secret values for installs that run without Vault."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel

from app.kernel.commons.time import utc_now


class SealedSecretValue(SQLModel, table=True):
    """One secret value, sealed with a key derived from ``SECRET_KEY``.

    Only the ``sealed`` secrets backend reads and writes this table. The
    locator is the same opaque storage address the Vault backend uses, so a
    secret's metadata and scoping stay in the secrets module either way; this
    table only replaces where the value itself is kept.
    """

    __tablename__ = "sealed_secret_values"

    locator: str = Field(primary_key=True, max_length=512)
    sealed_value: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
