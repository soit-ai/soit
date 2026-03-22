"""modelhub refactor tables

Revision ID: 20260128090000_modelhub_refactor
Revises: 20260127090000_appcenter_proj
Create Date: 2026-01-28 09:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260128090000_modelhub_refactor"
down_revision = "20260127090000_appcenter_proj"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "models" in tables:
        op.drop_table("models")

    if "platform_models" not in tables:
        op.create_table(
            "platform_models",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("provider_kind", sa.String(), nullable=False),
            sa.Column("model_id", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.Column("capabilities_json", sa.JSON(), nullable=True),
            sa.Column("context_window", sa.Integer(), nullable=True),
            sa.Column("max_output_tokens", sa.Integer(), nullable=True),
            sa.Column("lifecycle", sa.String(), nullable=True),
            sa.Column("raw_meta", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_unique_constraint(
            "uq_platform_models_kind_model",
            "platform_models",
            ["provider_kind", "model_id"],
        )
        op.create_index("ix_platform_models_tenant_workspace", "platform_models", ["tenant_id", "workspace_id"])
        op.create_index("ix_platform_models_kind", "platform_models", ["provider_kind"])
        op.create_index("ix_platform_models_model_id", "platform_models", ["model_id"])
    else:
        existing_columns = {col["name"] for col in inspector.get_columns("platform_models")}
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("platform_models")}

        if "tenant_id" not in existing_columns:
            op.add_column(
                "platform_models",
                sa.Column("tenant_id", sa.String(), nullable=True),
            )
        if "workspace_id" not in existing_columns:
            op.add_column(
                "platform_models",
                sa.Column("workspace_id", sa.String(), nullable=True),
            )

        op.execute("UPDATE platform_models SET tenant_id='platform' WHERE tenant_id IS NULL")
        op.execute("UPDATE platform_models SET workspace_id='platform' WHERE workspace_id IS NULL")

        op.alter_column("platform_models", "tenant_id", nullable=False)
        op.alter_column("platform_models", "workspace_id", nullable=False)

        if "ix_platform_models_tenant_workspace" not in existing_indexes:
            op.create_index(
                "ix_platform_models_tenant_workspace",
                "platform_models",
                ["tenant_id", "workspace_id"],
            )

    if "providers" not in tables:
        op.create_table(
            "providers",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("base_url", sa.String(), nullable=True),
            sa.Column("credential_ref", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("sync_policy_json", sa.JSON(), nullable=True),
            sa.Column("last_healthcheck_at", sa.DateTime(), nullable=True),
            sa.Column("last_healthcheck_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_providers_tenant_workspace", "providers", ["tenant_id", "workspace_id"])
        op.create_index("ix_providers_kind", "providers", ["kind"])

    if "provider_models" not in tables:
        op.create_table(
            "provider_models",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("provider_id", sa.String(), nullable=False),
            sa.Column("provider_kind", sa.String(), nullable=False),
            sa.Column("model_id", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("capabilities_json", sa.JSON(), nullable=True),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.Column("context_window", sa.Integer(), nullable=True),
            sa.Column("max_output_tokens", sa.Integer(), nullable=True),
            sa.Column("lifecycle", sa.String(), nullable=True),
            sa.Column("raw_meta", sa.JSON(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("platform_model_id", sa.String(), nullable=True),
            sa.Column("sync_status", sa.String(), nullable=False),
            sa.Column("user_overrides_json", sa.JSON(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_provider_models_tenant_workspace", "provider_models", ["tenant_id", "workspace_id"])
        op.create_index("ix_provider_models_provider", "provider_models", ["provider_id"])
        op.create_index("ix_provider_models_kind", "provider_models", ["provider_kind"])
        op.create_index("ix_provider_models_model_id", "provider_models", ["model_id"])
        op.create_index("ix_provider_models_platform_model_id", "provider_models", ["platform_model_id"])

    if "provider_model_tombstones" not in tables:
        op.create_table(
            "provider_model_tombstones",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("provider_id", sa.String(), nullable=False),
            sa.Column("platform_model_id", sa.String(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_provider_model_tombstones_workspace_provider",
            "provider_model_tombstones",
            ["tenant_id", "workspace_id", "provider_id"],
        )
        op.create_index(
            "ix_provider_model_tombstones_platform_model",
            "provider_model_tombstones",
            ["platform_model_id"],
        )

    if "provider_sync_jobs" not in tables:
        op.create_table(
            "provider_sync_jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("provider_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("diff_json", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_provider_sync_jobs_provider", "provider_sync_jobs", ["provider_id"])
        op.create_index(
            "ix_provider_sync_jobs_workspace",
            "provider_sync_jobs",
            ["tenant_id", "workspace_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_provider_sync_jobs_workspace", table_name="provider_sync_jobs")
    op.drop_index("ix_provider_sync_jobs_provider", table_name="provider_sync_jobs")
    op.drop_table("provider_sync_jobs")

    op.drop_index("ix_provider_model_tombstones_platform_model", table_name="provider_model_tombstones")
    op.drop_index("ix_provider_model_tombstones_workspace_provider", table_name="provider_model_tombstones")
    op.drop_table("provider_model_tombstones")

    op.drop_index("ix_provider_models_platform_model_id", table_name="provider_models")
    op.drop_index("ix_provider_models_model_id", table_name="provider_models")
    op.drop_index("ix_provider_models_kind", table_name="provider_models")
    op.drop_index("ix_provider_models_provider", table_name="provider_models")
    op.drop_index("ix_provider_models_tenant_workspace", table_name="provider_models")
    op.drop_table("provider_models")

    op.drop_index("ix_providers_kind", table_name="providers")
    op.drop_index("ix_providers_tenant_workspace", table_name="providers")
    op.drop_table("providers")

    op.drop_index("ix_platform_models_model_id", table_name="platform_models")
    op.drop_index("ix_platform_models_kind", table_name="platform_models")
    op.drop_index("ix_platform_models_tenant_workspace", table_name="platform_models")
    op.drop_constraint("uq_platform_models_kind_model", "platform_models", type_="unique")
    op.drop_table("platform_models")
