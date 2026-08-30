"""schedule_worker

Run the schedule worker loop in its own process.

Separate from the API for the same reason the outbox dispatcher is: a scheduler
that shares a process with request handling competes with it, and an API
restart should not be a gap in when jobs fire. Several replicas may run this;
the claim ensures each occurrence fires once.
"""

import asyncio
import logging

from app.infra.db.session import get_db_sync
from app.infra.telemetry import configure_telemetry
from app.settings.settings import settings
from app.wiring.schedule_worker import ScheduleWorker


async def main() -> None:
    """Start the schedule worker."""
    logging.basicConfig(level=settings.log_level or "INFO")
    configure_telemetry(service_name="soit-scheduler")
    poll_interval = max(1.0, float(settings.schedule_worker_poll_interval))
    logging.getLogger(__name__).info(
        "Starting schedule worker: poll_interval=%s lease_seconds=%s",
        poll_interval,
        settings.schedule_worker_lease_seconds,
    )
    worker = ScheduleWorker(
        get_db_sync,
        lease_seconds=int(settings.schedule_worker_lease_seconds),
    )
    await worker.run_loop(poll_interval=poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
