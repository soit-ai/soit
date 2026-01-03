""" models

AppCenter domain DB models (app + versions + marketplace).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON

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
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    name: str = Field()
    """App name."""
    
    description: Optional[str] = Field(default=None, nullable=True)
    """App description."""
    
    icon_url: Optional[str] = Field(default=None, nullable=True)
    """App icon URL."""
    
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
    
    id: str = Field(primary_key=True, default_factory=generate_app_version_id)
    """Version ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    app_id: str = Field(foreign_key="apps.id", index=True)
    """App ID (foreign key)."""
    
    version: str = Field()
    """Version string (e.g., "1.0.0")."""
    
    manifest_json: Dict[str, Any] = Field(sa_column=Column(JSON))
    """App manifest JSON (immutable)."""
    
    workflow_version_id: Optional[str] = Field(default=None, nullable=True)
    """Optional workflow version ID."""
    
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

