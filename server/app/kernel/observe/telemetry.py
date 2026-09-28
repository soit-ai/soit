"""Anonymous usage telemetry: what a report says, and nothing more.

Telemetry is off unless an operator turns it on (``TELEMETRY_ENABLED``). A
report covers one UTC day and holds only: a random installation id, the
version and edition, how the deployment is built (environment, process role,
vector, storage and secret backends), five counts for the day (governed runs,
gateway calls, metered calls, active workspaces, active principals) and the
enabled feature keys. It carries no names or ids of tenants, workspaces,
users or keys, no prompts, outputs, model names or addresses;
``docs/telemetry.md`` lists every field, and the preview endpoint shows the
exact report.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import distinct, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.entitlements.edition import EditionState
from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.usage import UsageDailyAggregate

REPORT_SCHEMA = 1
INSTALLATION_MARKER = "telemetry.installation"
"""The checkpoint row whose key is this installation's random id."""
DAILY_MARKER = "telemetry.daily_report"
"""One checkpoint row per UTC day a report was sent for, so replicas send it once."""


class TelemetrySink(Protocol):
    async def send(self, report: dict[str, Any]) -> None: ...


async def installation_id(db: AsyncSession) -> str:
    """This installation's random id, made the first time it is asked for."""
    query = (
        select(EventConsumerCheckpoint.event_id)
        .where(EventConsumerCheckpoint.consumer_name == INSTALLATION_MARKER)
        .order_by(EventConsumerCheckpoint.processed_at, EventConsumerCheckpoint.id)
        .limit(1)
    )
    existing = (await db.exec(query)).scalars().first()
    if existing:
        return str(existing)
    await try_claim_consumer_slot(db, consumer_name=INSTALLATION_MARKER, event_id=str(uuid4()))
    await db.commit()
    # Two processes may each have made one; the earliest is the id.
    return str((await db.exec(query)).scalars().one())


def _short(value: Any) -> str:
    return str(value or "").strip().lower()[:32]


def deployment_facts(settings: Any) -> dict[str, str]:
    storage_url = str(getattr(settings, "storage_url", "") or "")
    return {
        "environment": _short(getattr(settings, "environment", "")),
        "role": _short(getattr(settings, "soit_role", "all")),
        "vector_backend": _short(getattr(settings, "vector_backend", "")),
        "storage": _short(urlparse(storage_url).scheme if storage_url else "s3"),
        "secrets_backend": _short(getattr(settings, "secrets_backend", "")),
    }


async def daily_usage(db: AsyncSession, day: date) -> dict[str, int]:
    """The day's counts: top-level runs, gateway calls, and the usage aggregates."""
    start = datetime.combine(day, time.min, tzinfo=UTC)
    end = start + timedelta(days=1)
    runs, gateway = (
        await db.exec(
            select(
                func.count(Run.id),
                func.count(Run.id).filter(Run.source == "gateway"),
            ).where(Run.created_at >= start, Run.created_at < end, Run.parent_run_id.is_(None))
        )
    ).one()
    calls, workspaces, principals = (
        await db.exec(
            select(
                func.coalesce(func.sum(UsageDailyAggregate.call_count), 0),
                func.count(distinct(UsageDailyAggregate.workspace_id)),
                func.count(distinct(UsageDailyAggregate.user_id)).filter(UsageDailyAggregate.user_id != ""),
            ).where(UsageDailyAggregate.day == day)
        )
    ).one()
    return {
        "governed_runs": int(runs),
        "gateway_calls": int(gateway),
        "metered_calls": int(calls),
        "active_workspaces": int(workspaces),
        "active_principals": int(principals),
    }


async def build_report(db: AsyncSession, *, settings: Any, edition: EditionState, day: date) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "installation_id": await installation_id(db),
        "version": str(getattr(settings, "platform_version", "")),
        "edition": edition.edition,
        "day": day.isoformat(),
        "deployment": deployment_facts(settings),
        "usage": await daily_usage(db, day),
        "features": sorted(edition.enabled_features),
    }
