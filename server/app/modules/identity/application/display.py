"""Cross-module helpers for presenting identity data.

Other modules import from here (the identity public application surface)
instead of touching identity domain models directly.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.domain.models import User


def resolve_user_display_names(
    db: Session, user_ids: Iterable[str | None]
) -> dict[str, str]:
    """Map user ids to display names (name, falling back to email).

    Unknown or empty ids are omitted, so callers can fall back to the raw id.
    """
    ids = {user_id for user_id in user_ids if user_id}
    if not ids:
        return {}
    rows = db.execute(select(User).where(User.id.in_(ids))).scalars()
    return {user.id: (user.name or user.email) for user in rows}
