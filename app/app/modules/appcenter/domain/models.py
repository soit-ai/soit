""" models

AppCenter domain DB models (app + versions + marketplace).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Index, UniqueConstraint

from app.kernel.commons.time import utc_now
from app.kernel.commons.ids import generate_ulid


def generate_app_id() -> str:
    """Generate app ID."""
    return f"app_{generate_ulid()}"


def generate_app_version_id() -> str:
    """Generate app version ID."""
    return f"appv_{generate_ulid()}"


class App(SQLModel, table=True):
    """App model - workspace-scoped application definition."""
    
    __tablename__ = "apps"
    
    id: str = Field(primary_key=True, default_factory=generate_app_id)
    """App ID."""
    
    tenant_id: str = Field()
    """Tenant ID."""
    
    workspace_id: str = Field()
    """Workspace ID."""
    
    type: str = Field(default="WORKFLOW", index=True)
    """App type: WORKFLOW | CHAT | BOT | AGENT | DATASET."""

    status: str = Field(default="active", index=True)
    """App status: active | archived."""

    visibility: Optional[str] = Field(default="private", nullable=True)
    """Visibility: private | workspace | public."""

    name: str = Field()
    """App name."""
    
    description: Optional[str] = Field(default=None, nullable=True)
    """App description."""

    icon_url: Optional[str] = Field(default=None, nullable=True)
    """App icon URL."""

    metadata_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """App metadata (arbitrary JSON)."""
    
    current_version_id: Optional[str] = Field(default=None, nullable=True)
    """Current version ID (pointer to app_versions)."""
    
    published_version_id: Optional[str] = Field(default=None, nullable=True)
    """Published version ID (for marketplace)."""
    
    is_public: bool = Field(default=False)
    """Whether app is public (visible in marketplace)."""
    
    category: Optional[str] = Field(default=None, nullable=True)
    """App category."""
    
    tags: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    """App tags."""
    
    created_by: str = Field()
    """User ID who created this app."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class AppVersion(SQLModel, table=True):
    """AppVersion model - immutable app version."""
    
    __tablename__ = "app_versions"
    __table_args__ = (
        UniqueConstraint("app_id", "version", name="uq_app_versions_app_id_version"),
        Index("ix_app_versions_app_id_status", "app_id", "status"),
        Index("ix_app_versions_spec_checksum", "checksum"),
    )
    
    id: str = Field(primary_key=True, default_factory=generate_app_version_id)
    """Version ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    app_id: str = Field(foreign_key="apps.id", index=True)
    """App ID (foreign key)."""
    
    version: int = Field()
    """Monotonic version integer (per app)."""

    status: str = Field(default="draft")
    """Version status: draft | published | deprecated."""

    spec_schema: str = Field()
    """Spec schema identifier (e.g., workflow.v1, chat.v1)."""

    spec_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    """Runtime spec JSON (immutable)."""

    checksum: Optional[str] = Field(default=None, nullable=True, index=False)
    """SHA256 checksum of canonicalized spec_json."""

    created_from_version_id: Optional[str] = Field(default=None, nullable=True)
    """Source version ID used for cloning/rollback provenance."""
    
    changelog: Optional[str] = Field(default=None, nullable=True)
    """Version changelog."""
    
    created_by: str = Field()
    """User ID who created this version."""
    
    created_at: datetime = Field(default_factory=utc_now, index=True)
    """Creation timestamp."""


class AppMarket(SQLModel, table=True):
    """AppMarket model - marketplace listing."""
    
    __tablename__ = "app_market"
    
    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Market listing ID."""
    
    app_id: str = Field(foreign_key="apps.id", index=True, unique=True)
    """App ID (foreign key, unique)."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID (app owner)."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID (app owner)."""
    
    published_version_id: str = Field(foreign_key="app_versions.id")
    """Published version ID."""
    
    downloads_count: int = Field(default=0)
    """Number of downloads."""
    
    rating: Optional[float] = Field(default=None, nullable=True)
    """Average rating (1-5)."""
    
    reviews_count: int = Field(default=0)
    """Number of reviews."""
    
    featured: bool = Field(default=False)
    """Whether app is featured."""
    
    published_at: datetime = Field(default_factory=utc_now, index=True)
    """Publication timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class AppInstallation(SQLModel, table=True):
    """App installation record (workspace-scoped)."""

    __tablename__ = "app_installations"

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Installation ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    app_id: str = Field(foreign_key="apps.id", index=True)
    """Installed app ID."""

    installed_version_id: Optional[str] = Field(default=None, foreign_key="app_versions.id")
    """Installed app version ID."""

    status: str = Field(default="active")
    """Installation status."""

    installed_by: Optional[str] = Field(default=None)
    """User ID who installed."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class AppComponent(SQLModel, table=True):
    """Projected workflow node component."""

    __tablename__ = "app_components"
    __table_args__ = (
        UniqueConstraint("app_version_id", "component_id", name="uq_app_components_version_component"),
        Index("ix_app_components_tenant_workspace_app", "tenant_id", "workspace_id", "app_id"),
        Index("ix_app_components_app_version_id", "app_version_id"),
        Index("ix_app_components_component_type", "component_type"),
        Index("ix_app_components_spec_checksum", "spec_checksum"),
    )

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Component row ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    app_id: str = Field()
    """App ID."""

    app_version_id: str = Field()
    """App version ID."""

    component_id: str = Field()
    """Workflow node ID."""

    component_type: str = Field()
    """Workflow node type."""

    name: Optional[str] = Field(default=None, nullable=True)
    """Optional node name."""

    spec_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    """Node parameters payload."""

    ui_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """UI metadata such as position or group."""

    spec_checksum: str = Field()
    """Checksum aligned with app_versions.checksum."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class AppComponentEdge(SQLModel, table=True):
    """Projected workflow edge."""

    __tablename__ = "app_component_edges"
    __table_args__ = (
        UniqueConstraint("app_version_id", "edge_id", name="uq_app_component_edges_version_edge"),
        Index("ix_app_component_edges_app_version_id", "app_version_id"),
        Index("ix_app_component_edges_from_component_id", "from_component_id"),
        Index("ix_app_component_edges_to_component_id", "to_component_id"),
        Index("ix_app_component_edges_spec_checksum", "spec_checksum"),
    )

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Edge row ID."""

    tenant_id: str = Field()
    """Tenant ID."""

    workspace_id: str = Field()
    """Workspace ID."""

    app_id: str = Field()
    """App ID."""

    app_version_id: str = Field()
    """App version ID."""

    edge_id: str = Field()
    """Edge ID."""

    from_component_id: str = Field()
    """Source node ID."""

    to_component_id: str = Field()
    """Target node ID."""

    edge_spec_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    """Edge metadata payload."""

    spec_checksum: str = Field()
    """Checksum aligned with app_versions.checksum."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class AppVersionRef(SQLModel, table=True):
    """External reference index for app versions."""

    __tablename__ = "app_version_refs"
    __table_args__ = (
        UniqueConstraint(
            "app_version_id",
            "ref_type",
            "ref_id",
            "ref_key",
            "spec_path",
            name="uq_app_version_refs_unique_ref",
        ),
        Index("ix_app_version_refs_ref_id", "ref_type", "ref_id"),
        Index("ix_app_version_refs_ref_key", "ref_type", "ref_key"),
        Index("ix_app_version_refs_app_version_id", "app_version_id"),
        Index("ix_app_version_refs_spec_checksum", "spec_checksum"),
    )

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    """Reference row ID."""

    tenant_id: str = Field()
    """Tenant ID."""

    workspace_id: str = Field()
    """Workspace ID."""

    app_id: str = Field()
    """App ID."""

    app_version_id: str = Field()
    """App version ID."""

    ref_type: str = Field()
    """Reference type (tool/dataset/model/plugin/secret/app)."""

    ref_id: Optional[str] = Field(default=None, nullable=True)
    """Referenced resource ID (UUID-like)."""

    ref_key: Optional[str] = Field(default=None, nullable=True)
    """Referenced key (e.g., model ref)."""

    spec_path: Optional[str] = Field(default=None, nullable=True)
    """JSONPath location inside spec_json."""

    spec_checksum: str = Field()
    """Checksum aligned with app_versions.checksum."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
