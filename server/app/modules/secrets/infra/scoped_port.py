"""Tenant and workspace scoped runtime secret resolver."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.infra.db.session import get_db_sync
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.secrets.interface import (
    SecretLocator,
    SecretsPort,
    SecretValueStore,
    require_opaque_secret_id,
)
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.secrets.infra.repository import (
    SECRET_RESOLVED_EVENT_TYPE,
    SecretRepository,
)


class ScopedSecretsPort(SecretsPort):
    """Resolve secret IDs only after tenant/workspace metadata validation."""

    def __init__(
        self,
        *,
        ctx: RequestContext,
        value_store: SecretValueStore,
        db: Session | None = None,
    ) -> None:
        self.ctx = ctx
        self.value_store = value_store
        self.db = db

    async def get_secret(self, secret_id: str, **kwargs: Any) -> str:
        owns_session = self.db is None
        db = self.db or get_db_sync()
        try:
            try:
                normalized_id = require_opaque_secret_id(secret_id)
            except ValidationError:
                self._record_denial(db, resource_id=None, reason="invalid_id")
                if owns_session:
                    db.commit()
                raise

            secret = SecretRepository(db, self.ctx).get_by_id(normalized_id)
            if secret is None:
                self._record_denial(
                    db,
                    resource_id=normalized_id,
                    reason="not_resolvable_in_scope",
                )
                if owns_session:
                    db.commit()
                raise NotFoundError("Secret not found")

            value = await self.value_store.get_secret_value(
                locator=SecretLocator(secret.secret_ref),
                **kwargs,
            )
            self._record_resolution(db, resource_id=normalized_id)
            if owns_session:
                db.commit()
            return value
        finally:
            if owns_session:
                db.close()

    def _record_resolution(self, db: Session, *, resource_id: str) -> None:
        """Record that a secret was resolved, never what it resolved to.

        The value is deliberately absent: the evidence a reviewer needs is that
        this workspace resolved this secret at this time, which is also what
        makes the resolution count on the secrets surface a measurement rather
        than an estimate.
        """
        audit = AuditEvent(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            event_type=SECRET_RESOLVED_EVENT_TYPE,
            resource_type="secret",
            resource_id=resource_id,
            operation="resolve",
            actor_user_id=self.ctx.user_id,
            trace_id=self.ctx.trace_id,
            outcome="allowed",
            scope="workspace",
            payload_json={},
        )
        db.add(audit)
        db.flush()

    def _record_denial(
        self,
        db: Session,
        *,
        resource_id: str | None,
        reason: str,
    ) -> None:
        audit = AuditEvent(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            event_type="security.secret.access_denied",
            resource_type="secret",
            resource_id=resource_id,
            operation="resolve",
            actor_user_id=self.ctx.user_id,
            trace_id=self.ctx.trace_id,
            outcome="denied",
            scope="workspace",
            payload_json={"reason": reason},
        )
        db.add(audit)
        db.flush()
