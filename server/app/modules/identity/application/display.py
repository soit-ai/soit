"""Cross-module helpers for presenting identity data.

Other modules import from here (the identity public application surface)
instead of touching identity domain models directly.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.identity.domain.models import User


def _display_name_statement(user_ids: Iterable[str | None]):
    ids = {user_id for user_id in user_ids if user_id}
    if not ids:
        return None
    return select(User).where(User.id.in_(ids))


def resolve_user_display_names(
    db: Session, user_ids: Iterable[str | None]
) -> dict[str, str]:
    """Map user ids to display names (name, falling back to email).

    Unknown or empty ids are omitted, so callers can fall back to the raw id.
    """
    statement = _display_name_statement(user_ids)
    if statement is None:
        return {}
    rows = db.execute(statement).scalars()
    return {user.id: (user.name or user.email) for user in rows}


async def resolve_user_display_names_async(
    db: AsyncSession, user_ids: Iterable[str | None]
) -> dict[str, str]:
    """`resolve_user_display_names` for callers on an `AsyncSession`."""
    statement = _display_name_statement(user_ids)
    if statement is None:
        return {}
    rows = (await db.execute(statement)).scalars()
    return {user.id: (user.name or user.email) for user in rows}
