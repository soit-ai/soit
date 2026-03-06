"""registry

Helpers to resolve or create workspace-scoped apps and versions.
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.time import utc_now
from app.modules.appcenter.domain.models import App, AppVersion


class AppRegistry:
    """Resolve or create apps and versions for workspace defaults."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def get_or_create_app(
        self,
        *,
        name: str,
        app_type: str,
        description: Optional[str] = None,
        visibility: str = "private",
        status: str = "active",
    ) -> App:
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.type == app_type,
                App.name == name,
            )
        )
        existing = self.db.exec(query).first()
        if existing and hasattr(existing, "id"):
            return existing
        if existing:
            return existing[0]

        app = App(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            type=app_type,
            status=status,
            visibility=visibility,
            name=name,
            description=description,
            created_by=self.ctx.user_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app

    def get_or_create_version(
        self,
        app: App,
        *,
        spec_schema: str,
        spec_json: Dict[str, Any],
        status: str = "published",
    ) -> AppVersion:
        if app.current_version_id:
            version = self.db.get(AppVersion, app.current_version_id)
            if version and version.app_id == app.id:
                return version

        query = select(func.max(AppVersion.version)).where(
            and_(
                AppVersion.app_id == app.id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        max_val = self.db.exec(query).one()
        if hasattr(max_val, "_mapping"):
            max_val = max_val[0]
        elif isinstance(max_val, (list, tuple)):
            max_val = max_val[0] if max_val else None
        next_version = int(max_val or 0) + 1

        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=app.id,
            version=next_version,
            status=status,
            spec_schema=spec_schema,
            spec_json=spec_json,
            created_by=self.ctx.user_id,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        app.current_version_id = version.id
        app.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(app)
        return version
