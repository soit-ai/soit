"""Send one anonymous telemetry report a day, when the operator turned it on."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete

from app.kernel.entitlements.edition import current_edition
from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.observe.telemetry import DAILY_MARKER, TelemetrySink, build_report
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60 * 60


def report_day(now: datetime | None = None) -> date:
    """The last complete UTC day."""
    return (now or datetime.now(UTC)).astimezone(UTC).date() - timedelta(days=1)


def default_sink(settings: Any) -> TelemetrySink:
    from app.adapters.telemetry.http import HttpTelemetrySink

    return HttpTelemetrySink(str(settings.telemetry_endpoint))


async def preview_report(settings: Any, db: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """The report the next daily send would carry, whether or not telemetry is on."""
    return {
        "enabled": bool(settings.telemetry_enabled),
        "endpoint": str(settings.telemetry_endpoint),
        "report": await build_report(db, settings=settings, edition=current_edition(), day=report_day(now)),
    }


async def send_daily_report(
    settings: Any,
    session_factory: Callable[[], Any],
    sink: TelemetrySink,
    *,
    now: datetime | None = None,
) -> bool:
    """Send yesterday's report unless one was sent; True when this call sent it.

    The day is claimed before the report goes out, so replicas send it once;
    a report that fails to go out gives the claim back for the next check.
    """
    day = report_day(now).isoformat()
    async with session_factory() as session:
        if not await try_claim_consumer_slot(session, consumer_name=DAILY_MARKER, event_id=day):
            return False
        await session.commit()
        try:
            report = await build_report(
                session, settings=settings, edition=current_edition(), day=report_day(now)
            )
            await sink.send(report)
        except Exception:
            await session.rollback()
            await session.exec(
                delete(EventConsumerCheckpoint).where(
                    EventConsumerCheckpoint.consumer_name == DAILY_MARKER,
                    EventConsumerCheckpoint.event_id == day,
                )
            )
            await session.commit()
            raise
    logger.info("Sent the anonymous telemetry report for %s", day)
    return True


async def run_telemetry_loop(
    settings: Any,
    session_factory: Callable[[], Any],
    *,
    sink: TelemetrySink | None = None,
    interval_seconds: float = CHECK_INTERVAL_SECONDS,
) -> None:
    active_sink = sink or default_sink(settings)
    while True:
        try:
            await send_daily_report(settings, session_factory, active_sink)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Anonymous telemetry report not sent; retrying later: %s", exc)
        await asyncio.sleep(interval_seconds)
