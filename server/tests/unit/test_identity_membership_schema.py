"""Schema contracts for identity membership tables."""

from __future__ import annotations

import pytest
from sqlalchemy import PrimaryKeyConstraint, UniqueConstraint
from sqlmodel import SQLModel

from app.modules.identity.domain.models import TenantMembership, WorkspaceMembership


@pytest.mark.parametrize(
    ("model", "constraint_name", "columns"),
    [
        (TenantMembership, "uq_tenant_membership", ["tenant_id", "user_id"]),
        (
            WorkspaceMembership,
            "uq_workspace_membership",
            ["tenant_id", "workspace_id", "user_id"],
        ),
    ],
)
def test_membership_identity_is_expressed_by_one_named_primary_key(
    model: type[SQLModel], constraint_name: str, columns: list[str]
) -> None:
    constraints = model.__table__.constraints
    primary_keys = [item for item in constraints if isinstance(item, PrimaryKeyConstraint)]
    unique_constraints = [
        item for item in constraints if isinstance(item, UniqueConstraint)
    ]

    assert len(primary_keys) == 1
    assert primary_keys[0].name == constraint_name
    assert [column.name for column in primary_keys[0].columns] == columns
    assert unique_constraints == []
