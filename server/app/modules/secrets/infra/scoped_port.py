"""Tenant and workspace scoped runtime secret resolver."""

from __future__ import annotations

import time
import weakref
from collections import OrderedDict
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_session_local
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.secrets.interface import (
    SecretLocator,
    SecretsPort,
    SecretValueStore,
    require_opaque_secret_id,
)
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.secrets.domain.models import Secret
from app.modules.secrets.infra.repository import SECRET_RESOLVED_EVENT_TYPE
from app.settings.settings import settings

_MAX_CACHED_VALUES = 1024

_ValueKey = tuple[str, str, datetime | None, datetime | None]


class _ValueCache:
    """Resolved values for a short while, keyed by the secret's rotation state.

    Every model call resolves its provider credential, and each resolution
    went to Vault. The key carries the row's rotation and update timestamps,
    so rotating or editing a secret moves every process to a new key at once;
    the TTL only bounds how long a value sits in memory. Deleted secrets never
    reach the cache: the metadata lookup in front of it refuses them.
    """

    def __init__(self) -> None:
        self._entries: OrderedDict[_ValueKey, tuple[float, str]] = OrderedDict()

    def get(self, key: _ValueKey, now: float) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= now:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def put(self, key: _ValueKey, value: str, expires_at: float) -> None:
        self._entries[key] = (expires_at, value)
        self._entries.move_to_end(key)
        while len(self._entries) > _MAX_CACHED_VALUES:
            self._entries.popitem(last=False)


_value_caches: weakref.WeakKeyDictionary[SecretValueStore, _ValueCache] = (
    weakref.WeakKeyDictionary()
)


def _cache_for(store: SecretValueStore) -> _ValueCache:
    cache = _value_caches.get(store)
    if cache is None:
        cache = _ValueCache()
        _value_caches[store] = cache
    return cache


class ScopedSecretsPort(SecretsPort):
    """Resolve secret IDs only after tenant/workspace metadata validation.

    The port runs inside an execution (a tool call, a model call) on that
    execution's `AsyncSession`; without one it opens and commits its own.
    """

    def __init__(
        self,
        *,
        ctx: RequestContext,
        value_store: SecretValueStore,
        db: AsyncSession | None = None,
    ) -> None:
        self.ctx = ctx
        self.value_store = value_store
        self.db = db

    async def get_secret(self, secret_id: str, **kwargs: Any) -> str:
        owns_session = self.db is None
        db = self.db or get_async_session_local()()
        try:
            try:
                normalized_id = require_opaque_secret_id(secret_id)
            except ValidationError:
                await self._record_denial(db, resource_id=None, reason="invalid_id")
                if owns_session:
                    await db.commit()
                raise

            secret = await self._find_secret(db, normalized_id)
            if secret is None:
                await self._record_denial(
                    db,
                    resource_id=normalized_id,
                    reason="not_resolvable_in_scope",
                )
                if owns_session:
                    await db.commit()
                raise NotFoundError("Secret not found")

            value = await self._read_value(secret, **kwargs)
            # Recorded on every resolution, cached or not: the count is a
            # measurement of use, not of trips to the value store.
            await self._record_resolution(db, resource_id=normalized_id)
            if owns_session:
                await db.commit()
            return value
        finally:
            if owns_session:
                await db.close()

    async def _read_value(self, secret: Secret, **kwargs: Any) -> str:
        ttl = float(settings.secret_value_cache_seconds)
        if ttl <= 0 or kwargs:
            return await self.value_store.get_secret_value(
                locator=SecretLocator(secret.secret_ref),
                **kwargs,
            )
        key: _ValueKey = (secret.id, secret.secret_ref, secret.last_rotated_at, secret.updated_at)
        cache = _cache_for(self.value_store)
        now = time.monotonic()
        cached = cache.get(key, now)
        if cached is not None:
            return cached
        value = await self.value_store.get_secret_value(locator=SecretLocator(secret.secret_ref))
        cache.put(key, value, now + ttl)
        return value

    async def _find_secret(self, db: AsyncSession, secret_id: str) -> Secret | None:
        query = select(Secret).where(
            and_(
                Secret.id == secret_id,
                Secret.tenant_id == self.ctx.tenant_id,
                Secret.workspace_id == self.ctx.workspace_id,
                Secret.deleted_at.is_(None),
            )
        )
        return (await db.exec(query)).scalars().first()

    async def _record_resolution(self, db: AsyncSession, *, resource_id: str) -> None:
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
        await db.flush()

    async def _record_denial(
        self,
        db: AsyncSession,
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
        await db.flush()
