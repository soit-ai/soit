"""publish_service

App publish pipeline with projections.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, update, delete

from app.kernel.commons.errors import ValidationError, NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.commons.serialization import checksum_json
from app.kernel.specs.validator import validate_runtime_spec
from app.kernel.projections.workflow_projection import (
    build_workflow_components,
    build_workflow_edges,
    build_workflow_refs,
)
from app.kernel.projections.chat_projection import build_chat_refs
from app.kernel.projections.bot_projection import build_bot_refs
from app.kernel.projections.agent_projection import build_agent_refs
from app.kernel.contracts.context import RequestContext
from app.modules.appcenter.domain.models import (
    App,
    AppVersion,
    AppComponent,
    AppComponentEdge,
    AppVersionRef,
)
from app.modules.appcenter.application.preflight import PreflightChecker


class AppPublishService:
    """Publish pipeline for app versions."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx
        self.preflight = PreflightChecker(db, ctx)

    def _get_app(self, app_id: str) -> App:
        app = self.db.get(App, app_id)
        if not app or app.tenant_id != self.ctx.tenant_id or app.workspace_id != self.ctx.workspace_id:
            raise NotFoundError(f"App not found: {app_id}")
        return app

    def _get_version(self, version_id: str) -> AppVersion:
        version = self.db.get(AppVersion, version_id)
        if not version or version.tenant_id != self.ctx.tenant_id or version.workspace_id != self.ctx.workspace_id:
            raise NotFoundError(f"App version not found: {version_id}")
        return version

    def publish(self, app_id: str, version_id: str, *, run_preflight: bool = False) -> AppVersion:
        """Publish an app version with projections."""
        app = self._get_app(app_id)
        version = self._get_version(version_id)
        if version.app_id != app.id:
            raise ValidationError("Version does not belong to app")

        spec_schema = (version.spec_schema or "").lower()
        if not spec_schema:
            raise ValidationError("Spec schema is required")

        validate_runtime_spec(spec_schema, version.spec_json, raise_on_error=True)

        checksum = checksum_json(version.spec_json)
        if version.status == "published":
            if version.checksum and version.checksum != checksum:
                raise ValidationError("Published version is immutable")
        if version.status not in ("draft", "published"):
            raise ValidationError("Only draft or published versions can be published")

        if run_preflight:
            self.preflight.check(version.spec_json, spec_schema)

        if version.status != "published":
            version.status = "published"
        version.checksum = checksum

        # Mark older published versions as deprecated
        self.db.exec(
            update(AppVersion)
            .where(
                and_(
                    AppVersion.app_id == app.id,
                    AppVersion.tenant_id == self.ctx.tenant_id,
                    AppVersion.workspace_id == self.ctx.workspace_id,
                    AppVersion.status == "published",
                    AppVersion.id != version.id,
                )
            )
            .values(status="deprecated")
        )

        app.current_version_id = version.id
        app.updated_at = utc_now()
        self.db.add(app)

        # Build projections
        if spec_schema == "workflow.v1":
            self._build_workflow_projections(app, version, checksum)
        elif spec_schema == "chat.v1":
            self._build_chat_projections(app, version, checksum)
        elif spec_schema == "bot.v1":
            self._build_bot_projections(app, version, checksum)
        elif spec_schema == "agent.v1":
            self._build_agent_projections(app, version, checksum)

        self.db.commit()
        self.db.refresh(version)
        return version

    def rebuild_projections(self, app_id: str, version_id: str) -> AppVersion:
        """Rebuild projections for a version without changing status."""
        app = self._get_app(app_id)
        version = self._get_version(version_id)
        if version.app_id != app.id:
            raise ValidationError("Version does not belong to app")

        checksum = checksum_json(version.spec_json)
        version.checksum = checksum
        spec_schema = (version.spec_schema or "").lower()
        if spec_schema == "workflow.v1":
            self._build_workflow_projections(app, version, checksum)
        elif spec_schema == "chat.v1":
            self._build_chat_projections(app, version, checksum)
        elif spec_schema == "bot.v1":
            self._build_bot_projections(app, version, checksum)
        elif spec_schema == "agent.v1":
            self._build_agent_projections(app, version, checksum)
        self.db.commit()
        self.db.refresh(version)
        return version

    def _build_chat_projections(self, app: App, version: AppVersion, checksum: str) -> None:
        refs = build_chat_refs(version.spec_json)

        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum != checksum,
                )
            )
        )
        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum == checksum,
                )
            )
        )

        for ref in refs:
            self.db.add(
                AppVersionRef(
                    tenant_id=app.tenant_id,
                    workspace_id=app.workspace_id,
                    app_id=app.id,
                    app_version_id=version.id,
                    ref_type=ref.get("ref_type") or "",
                    ref_id=ref.get("ref_id"),
                    ref_key=ref.get("ref_key"),
                    spec_path=ref.get("spec_path"),
                    spec_checksum=checksum,
                )
            )

    def _build_bot_projections(self, app: App, version: AppVersion, checksum: str) -> None:
        refs = build_bot_refs(version.spec_json)

        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum != checksum,
                )
            )
        )
        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum == checksum,
                )
            )
        )

        for ref in refs:
            self.db.add(
                AppVersionRef(
                    tenant_id=app.tenant_id,
                    workspace_id=app.workspace_id,
                    app_id=app.id,
                    app_version_id=version.id,
                    ref_type=ref.get("ref_type") or "",
                    ref_id=ref.get("ref_id"),
                    ref_key=ref.get("ref_key"),
                    spec_path=ref.get("spec_path"),
                    spec_checksum=checksum,
                )
            )

    def _build_agent_projections(self, app: App, version: AppVersion, checksum: str) -> None:
        refs = build_agent_refs(version.spec_json)

        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum != checksum,
                )
            )
        )
        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum == checksum,
                )
            )
        )

        for ref in refs:
            self.db.add(
                AppVersionRef(
                    tenant_id=app.tenant_id,
                    workspace_id=app.workspace_id,
                    app_id=app.id,
                    app_version_id=version.id,
                    ref_type=ref.get("ref_type") or "",
                    ref_id=ref.get("ref_id"),
                    ref_key=ref.get("ref_key"),
                    spec_path=ref.get("spec_path"),
                    spec_checksum=checksum,
                )
            )

    def _build_workflow_projections(self, app: App, version: AppVersion, checksum: str) -> None:
        components = build_workflow_components(version.spec_json)
        edges = build_workflow_edges(version.spec_json)
        refs = build_workflow_refs(version.spec_json)

        # Clean old projections for other checksums
        self.db.exec(
            delete(AppComponent).where(
                and_(
                    AppComponent.app_version_id == version.id,
                    AppComponent.spec_checksum != checksum,
                )
            )
        )
        self.db.exec(
            delete(AppComponentEdge).where(
                and_(
                    AppComponentEdge.app_version_id == version.id,
                    AppComponentEdge.spec_checksum != checksum,
                )
            )
        )
        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum != checksum,
                )
            )
        )

        # Remove existing projections for same checksum (idempotent rebuild)
        self.db.exec(
            delete(AppComponent).where(
                and_(
                    AppComponent.app_version_id == version.id,
                    AppComponent.spec_checksum == checksum,
                )
            )
        )
        self.db.exec(
            delete(AppComponentEdge).where(
                and_(
                    AppComponentEdge.app_version_id == version.id,
                    AppComponentEdge.spec_checksum == checksum,
                )
            )
        )
        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_version_id == version.id,
                    AppVersionRef.spec_checksum == checksum,
                )
            )
        )

        for item in components:
            if not item.get("component_id"):
                continue
            self.db.add(
                AppComponent(
                    tenant_id=app.tenant_id,
                    workspace_id=app.workspace_id,
                    app_id=app.id,
                    app_version_id=version.id,
                    component_id=item["component_id"],
                    component_type=item.get("component_type") or "unknown",
                    name=item.get("name"),
                    spec_json=item.get("spec_json") or {},
                    ui_json=item.get("ui_json"),
                    spec_checksum=checksum,
                )
            )

        for edge in edges:
            if not edge.get("edge_id"):
                continue
            self.db.add(
                AppComponentEdge(
                    tenant_id=app.tenant_id,
                    workspace_id=app.workspace_id,
                    app_id=app.id,
                    app_version_id=version.id,
                    edge_id=edge["edge_id"],
                    from_component_id=edge.get("from_component_id") or "",
                    to_component_id=edge.get("to_component_id") or "",
                    edge_spec_json=edge.get("edge_spec_json") or {},
                    spec_checksum=checksum,
                )
            )

        for ref in refs:
            self.db.add(
                AppVersionRef(
                    tenant_id=app.tenant_id,
                    workspace_id=app.workspace_id,
                    app_id=app.id,
                    app_version_id=version.id,
                    ref_type=ref.get("ref_type") or "",
                    ref_id=ref.get("ref_id"),
                    ref_key=ref.get("ref_key"),
                    spec_path=ref.get("spec_path"),
                    spec_checksum=checksum,
                )
            )
