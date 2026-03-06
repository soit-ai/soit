"""config_provider

Resolve chat configuration from unified apps/app_versions.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError
from app.modules.appcenter.application.registry import AppRegistry
from app.modules.appcenter.application.publish_service import AppPublishService
from app.modules.appcenter.domain.models import App, AppVersion


class ChatConfigProvider:
    """Chat config provider backed by apps/app_versions."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self._cache: Optional[Tuple[App, AppVersion]] = None

    def _default_spec(self) -> Dict[str, Any]:
        return {
            "runtime": "chat_runtime_v1",
            "model": {
                "ref_key": "model:openai:gpt-5.1",
                "params": {
                    "temperature": 0.7,
                },
            },
            "system_prompt": None,
            "tools": {
                "allowlist": None,
                "configs": None,
            },
            "rag": None,
            "memory": None,
            "limits": {
                "max_tokens": None,
                "timeout_ms": None,
                "budget": None,
                "history_limit": None,
            },
            "ui": None,
        }

    def _get_app(self, app_id: str) -> App:
        query = select(App).where(
            and_(
                App.id == app_id,
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        app = result if isinstance(result, App) else result[0] if result else None
        if not app:
            raise NotFoundError(f"Chat app not found: {app_id}")
        if app.type != "CHAT":
            raise NotFoundError(f"Chat app not found: {app_id}")
        return app

    def resolve(self, app_id: Optional[str] = None) -> Tuple[App, AppVersion, Dict[str, Any]]:
        """Resolve chat app + version + spec."""
        if app_id:
            app = self._get_app(app_id)
            version_id = app.current_version_id
            if not version_id:
                raise NotFoundError("Chat app has no current version")
            version = self.db.get(AppVersion, version_id)
            if not version or version.app_id != app.id:
                raise NotFoundError("Chat app version not found")
            return app, version, version.spec_json or {}

        if self._cache:
            app, version = self._cache
            return app, version, version.spec_json or {}

        registry = AppRegistry(self.db, self.ctx)
        app = registry.get_or_create_app(
            name="Chat Default",
            app_type="CHAT",
            description="Default chat configuration",
        )
        version = registry.get_or_create_version(
            app,
            spec_schema="chat.v1",
            spec_json=self._default_spec(),
            status="published",
        )
        if not version.checksum:
            publisher = AppPublishService(self.db, self.ctx)
            publisher.publish(app.id, version.id)
            self.db.refresh(version)
        self._cache = (app, version)
        return app, version, version.spec_json or {}
