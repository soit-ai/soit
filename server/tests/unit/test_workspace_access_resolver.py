"""Workspace access resolves in one round trip and keeps every refusal it had.

The resolver is the database read every authenticated request makes; it
used to be five primary-key reads in sequence. These tests pin the single
statement and the decisions it still has to make from that one row.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import event
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ForbiddenError, UnauthorizedError
from app.kernel.commons.time import utc_now
from app.modules.identity.domain.models import (
    Tenant,
    TenantMembership,
    UserMfa,
    UserSession,
    Workspace,
    WorkspaceMembership,
)
from app.modules.identity.infra import workspace_access
from app.modules.identity.infra.workspace_access import DatabaseWorkspaceAccessResolver

TENANT = "tenant-access"
WORKSPACE = "workspace-access"
USER = "user-access"


async def _seed(
    async_db,
    *,
    require_mfa: bool = False,
    workspace_llm_rate: int | None = None,
    content_capture: str = "full",
) -> None:
    async_db.add(Tenant(id=TENANT, name="Access tenant", llm_rate_limit_per_minute=30, tool_daily_quota=500))
    async_db.add(
        Workspace(
            id=WORKSPACE,
            tenant_id=TENANT,
            name="Access workspace",
            require_mfa=require_mfa,
            llm_rate_limit_per_minute=workspace_llm_rate,
            content_capture=content_capture,
        )
    )
    async_db.add(TenantMembership(tenant_id=TENANT, user_id=USER, role="Admin"))
    async_db.add(
        WorkspaceMembership(tenant_id=TENANT, workspace_id=WORKSPACE, user_id=USER, role="Editor")
    )
    await async_db.commit()


@pytest.fixture
def resolver(async_db, monkeypatch) -> DatabaseWorkspaceAccessResolver:
    engine = async_db.bind
    monkeypatch.setattr(
        workspace_access,
        "get_async_session_local",
        lambda: (lambda: AsyncSession(bind=engine, expire_on_commit=False)),
    )
    return DatabaseWorkspaceAccessResolver()


@pytest.fixture
def statements(async_db) -> list[str]:
    seen: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        seen.append(statement)

    engine = async_db.bind.sync_engine
    event.listen(engine, "before_cursor_execute", record)
    yield seen
    event.remove(engine, "before_cursor_execute", record)


@pytest.mark.asyncio
async def test_access_resolves_in_one_statement_with_workspace_overrides(async_db, resolver, statements) -> None:
    await _seed(async_db, workspace_llm_rate=5)
    statements.clear()

    access = await resolver.resolve(TENANT, WORKSPACE, USER)

    assert access is not None
    assert (access.tenant_role, access.workspace_role) == ("Admin", "Editor")
    assert access.llm_rate_limit_per_minute == 5  # workspace wins
    assert access.tool_daily_quota == 500  # tenant fills the gap
    assert len(statements) == 1


@pytest.mark.asyncio
async def test_missing_membership_yields_no_access(async_db, resolver) -> None:
    await _seed(async_db)

    assert await resolver.resolve(TENANT, WORKSPACE, "somebody-else") is None
    assert await resolver.resolve(TENANT, "another-workspace", USER) is None
    assert await resolver.resolve("another-tenant", WORKSPACE, USER) is None


@pytest.mark.asyncio
async def test_a_dead_session_is_refused_before_membership_is_considered(async_db, resolver) -> None:
    await _seed(async_db)
    async_db.add(
        UserSession(
            id="sess-ended",
            tenant_id=TENANT,
            user_id=USER,
            refresh_token_hash="hash-ended",
            status="ended",
            expires_at=utc_now() + timedelta(hours=1),
        )
    )
    async_db.add(
        UserSession(
            id="sess-expired",
            tenant_id=TENANT,
            user_id=USER,
            refresh_token_hash="hash-expired",
            status="active",
            expires_at=utc_now() - timedelta(minutes=1),
        )
    )
    async_db.add(
        UserSession(
            id="sess-live",
            tenant_id=TENANT,
            user_id=USER,
            refresh_token_hash="hash-live",
            status="active",
            expires_at=utc_now() + timedelta(hours=1),
        )
    )
    await async_db.commit()

    with pytest.raises(UnauthorizedError):
        await resolver.resolve(TENANT, WORKSPACE, USER, session_id="sess-ended")
    with pytest.raises(UnauthorizedError):
        await resolver.resolve(TENANT, WORKSPACE, USER, session_id="sess-expired")
    with pytest.raises(UnauthorizedError):
        await resolver.resolve(TENANT, WORKSPACE, USER, session_id="sess-unknown")
    # Even a non-member is told the session is dead, not that they lack access.
    with pytest.raises(UnauthorizedError):
        await resolver.resolve("another-tenant", WORKSPACE, USER, session_id="sess-ended")
    assert await resolver.resolve(TENANT, WORKSPACE, USER, session_id="sess-live") is not None


@pytest.mark.asyncio
async def test_mfa_requirement_needs_an_active_enrolment(async_db, resolver) -> None:
    await _seed(async_db, require_mfa=True)

    with pytest.raises(ForbiddenError) as refused:
        await resolver.resolve(TENANT, WORKSPACE, USER)
    assert refused.value.details["reason"] == "mfa_required"

    enrolment = UserMfa(user_id=USER, secret_sealed="sealed", status="pending")
    async_db.add(enrolment)
    await async_db.commit()
    with pytest.raises(ForbiddenError):
        await resolver.resolve(TENANT, WORKSPACE, USER)

    enrolment.status = "active"
    async_db.add(enrolment)
    await async_db.commit()
    assert await resolver.resolve(TENANT, WORKSPACE, USER) is not None

@pytest.mark.asyncio
async def test_the_workspace_content_capture_rides_along(async_db, resolver, statements) -> None:
    await _seed(async_db, content_capture="metadata_only")
    statements.clear()

    access = await resolver.resolve(TENANT, WORKSPACE, USER)

    assert access is not None
    assert access.content_capture == "metadata_only"
    assert len(statements) == 1
