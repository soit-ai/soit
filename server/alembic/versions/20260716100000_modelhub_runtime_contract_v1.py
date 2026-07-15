"""Enforce scoped ModelHub runtime uniqueness.

Revision ID: 20260716100000
Revises: 20260716090000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716100000"
down_revision: str | None = "20260716090000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _abort_on_duplicates(
    table: str,
    columns: tuple[str, ...],
    *,
    where: str | None = None,
) -> None:
    column_sql = ", ".join(columns)
    where_sql = f" WHERE {where}" if where else ""
    duplicate = op.get_bind().execute(
        sa.text(
            f"SELECT {column_sql}, COUNT(*) AS duplicate_count "
            f"FROM {table}{where_sql} GROUP BY {column_sql} "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            f"Cannot enforce ModelHub uniqueness on {table}({column_sql}); "
            "duplicate rows must be resolved first"
        )


def upgrade() -> None:
    _abort_on_duplicates("platform_models", ("provider_kind", "model_id"))
    _abort_on_duplicates(
        "providers",
        ("tenant_id", "workspace_id", "slug"),
        where="slug IS NOT NULL",
    )
    _abort_on_duplicates(
        "providers",
        ("tenant_id", "workspace_id", "name"),
    )
    _abort_on_duplicates(
        "provider_models",
        ("tenant_id", "workspace_id", "provider_id", "model_id"),
    )

    op.create_index(
        "uq_platform_models_provider_kind_model_id",
        "platform_models",
        ["provider_kind", "model_id"],
        unique=True,
    )
    op.create_index(
        "uq_providers_scope_slug",
        "providers",
        ["tenant_id", "workspace_id", "slug"],
        unique=True,
    )
    op.create_index(
        "uq_providers_scope_name",
        "providers",
        ["tenant_id", "workspace_id", "name"],
        unique=True,
    )
    op.create_index(
        "uq_provider_models_scope_provider_model_id",
        "provider_models",
        ["tenant_id", "workspace_id", "provider_id", "model_id"],
        unique=True,
    )
    op.create_index(
        "ix_providers_scope_status",
        "providers",
        ["tenant_id", "workspace_id", "status"],
    )
    op.create_index(
        "ix_provider_models_scope_status",
        "provider_models",
        ["tenant_id", "workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_models_scope_status", table_name="provider_models")
    op.drop_index("ix_providers_scope_status", table_name="providers")
    op.drop_index(
        "uq_provider_models_scope_provider_model_id",
        table_name="provider_models",
    )
    op.drop_index("uq_providers_scope_name", table_name="providers")
    op.drop_index("uq_providers_scope_slug", table_name="providers")
    op.drop_index(
        "uq_platform_models_provider_kind_model_id",
        table_name="platform_models",
    )
