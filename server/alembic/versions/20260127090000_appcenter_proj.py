"""Historical AppCenter projection revision retained for migration lineage.

This revision still references pre-convergence app-era tables because it is
part of the immutable Alembic chain. New runtime code must use Agent terms.

Revision ID: 20260127090000_appcenter_proj
Revises: 20260126230000_baseline_apps
Create Date: 2026-01-27 09:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260127090000_appcenter_proj"
down_revision = "20260126230000_baseline_apps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = set(inspector.get_table_names())
    if "app_versions" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("app_versions")}
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("app_versions")}

        if "checksum" not in existing_columns:
            op.add_column("app_versions", sa.Column("checksum", sa.String(), nullable=True))
        if "created_from_version_id" not in existing_columns:
            op.add_column(
                "app_versions",
                sa.Column("created_from_version_id", sa.String(), nullable=True),
            )
        if "ix_app_versions_spec_checksum" not in existing_indexes:
            op.create_index("ix_app_versions_spec_checksum", "app_versions", ["checksum"])

    if "app_components" not in existing_tables:
        op.create_table(
            "app_components",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("app_id", sa.String(), nullable=False),
            sa.Column("app_version_id", sa.String(), nullable=False),
            sa.Column("component_id", sa.String(), nullable=False),
            sa.Column("component_type", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("spec_json", sa.JSON(), nullable=False),
            sa.Column("ui_json", sa.JSON(), nullable=True),
            sa.Column("spec_checksum", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_unique_constraint(
            "uq_app_components_version_component",
            "app_components",
            ["app_version_id", "component_id"],
        )
        op.create_index(
            "ix_app_components_tenant_workspace_app",
            "app_components",
            ["tenant_id", "workspace_id", "app_id"],
        )
        op.create_index("ix_app_components_app_version_id", "app_components", ["app_version_id"])
        op.create_index("ix_app_components_component_type", "app_components", ["component_type"])
        op.create_index("ix_app_components_spec_checksum", "app_components", ["spec_checksum"])

    if "app_component_edges" not in existing_tables:
        op.create_table(
            "app_component_edges",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("app_id", sa.String(), nullable=False),
            sa.Column("app_version_id", sa.String(), nullable=False),
            sa.Column("edge_id", sa.String(), nullable=False),
            sa.Column("from_component_id", sa.String(), nullable=False),
            sa.Column("to_component_id", sa.String(), nullable=False),
            sa.Column("edge_spec_json", sa.JSON(), nullable=False),
            sa.Column("spec_checksum", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_unique_constraint(
            "uq_app_component_edges_version_edge",
            "app_component_edges",
            ["app_version_id", "edge_id"],
        )
        op.create_index(
            "ix_app_component_edges_app_version_id",
            "app_component_edges",
            ["app_version_id"],
        )
        op.create_index(
            "ix_app_component_edges_from_component_id",
            "app_component_edges",
            ["from_component_id"],
        )
        op.create_index(
            "ix_app_component_edges_to_component_id",
            "app_component_edges",
            ["to_component_id"],
        )
        op.create_index(
            "ix_app_component_edges_spec_checksum",
            "app_component_edges",
            ["spec_checksum"],
        )

    if "app_version_refs" not in existing_tables:
        op.create_table(
            "app_version_refs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("app_id", sa.String(), nullable=False),
            sa.Column("app_version_id", sa.String(), nullable=False),
            sa.Column("ref_type", sa.String(), nullable=False),
            sa.Column("ref_id", sa.String(), nullable=True),
            sa.Column("ref_key", sa.String(), nullable=True),
            sa.Column("spec_path", sa.String(), nullable=True),
            sa.Column("spec_checksum", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_unique_constraint(
            "uq_app_version_refs_unique_ref",
            "app_version_refs",
            ["app_version_id", "ref_type", "ref_id", "ref_key", "spec_path"],
        )
        op.create_index("ix_app_version_refs_ref_id", "app_version_refs", ["ref_type", "ref_id"])
        op.create_index("ix_app_version_refs_ref_key", "app_version_refs", ["ref_type", "ref_key"])
        op.create_index(
            "ix_app_version_refs_app_version_id",
            "app_version_refs",
            ["app_version_id"],
        )
        op.create_index(
            "ix_app_version_refs_spec_checksum",
            "app_version_refs",
            ["spec_checksum"],
        )


def downgrade() -> None:
    op.drop_index("ix_app_version_refs_spec_checksum", table_name="app_version_refs")
    op.drop_index("ix_app_version_refs_app_version_id", table_name="app_version_refs")
    op.drop_index("ix_app_version_refs_ref_key", table_name="app_version_refs")
    op.drop_index("ix_app_version_refs_ref_id", table_name="app_version_refs")
    op.drop_constraint("uq_app_version_refs_unique_ref", "app_version_refs", type_="unique")
    op.drop_table("app_version_refs")

    op.drop_index("ix_app_component_edges_spec_checksum", table_name="app_component_edges")
    op.drop_index("ix_app_component_edges_to_component_id", table_name="app_component_edges")
    op.drop_index("ix_app_component_edges_from_component_id", table_name="app_component_edges")
    op.drop_index("ix_app_component_edges_app_version_id", table_name="app_component_edges")
    op.drop_constraint("uq_app_component_edges_version_edge", "app_component_edges", type_="unique")
    op.drop_table("app_component_edges")

    op.drop_index("ix_app_components_spec_checksum", table_name="app_components")
    op.drop_index("ix_app_components_component_type", table_name="app_components")
    op.drop_index("ix_app_components_app_version_id", table_name="app_components")
    op.drop_index("ix_app_components_tenant_workspace_app", table_name="app_components")
    op.drop_constraint("uq_app_components_version_component", "app_components", type_="unique")
    op.drop_table("app_components")

    op.drop_index("ix_app_versions_spec_checksum", table_name="app_versions")
    op.drop_column("app_versions", "created_from_version_id")
    op.drop_column("app_versions", "checksum")
