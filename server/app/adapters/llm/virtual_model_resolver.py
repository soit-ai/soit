"""Database-backed lookup of a workspace's virtual models."""

from __future__ import annotations

from collections.abc import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_session_local
from app.kernel.contracts.context import RequestContext
from app.modules.modelhub.infra.repository import VirtualModelRepository


class DatabaseVirtualModelResolver:
    """Resolve ``vmodel:{slug}`` to its ordered targets.

    Each lookup uses a session of its own, like the provider resolver: the
    call's session is released while the model answers, and a lookup must
    not hold it open.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None) -> None:
        self._session_factory = session_factory

    def _session(self) -> AsyncSession:
        if self._session_factory is not None:
            return self._session_factory()
        return get_async_session_local()()

    async def resolve_targets(self, ctx: RequestContext, slug: str) -> list[str] | None:
        db = self._session()
        try:
            model = await VirtualModelRepository(db, ctx).get_by_slug(slug)
            if model is None or model.status != "active":
                return None
            targets = [str(target) for target in model.targets_json or []]
            return targets or None
        finally:
            await db.close()
