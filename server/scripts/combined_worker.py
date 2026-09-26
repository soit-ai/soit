"""Run every background worker of a small install in one process.

The lite profile (docker/docker-compose.lite.yml) runs the knowledge ingest
worker, the outbox dispatcher with its retention sweep, and the schedule
worker here instead of in three containers. Each loop is the same one its
dedicated script runs, and each claims work through the same leases, so a
deployment can later split them out without changing behaviour. The chat
interaction worker stays in the API process for the lite profile.

The image this runs in must include the knowledge-worker extras (docling),
which the ingest loop needs.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from prometheus_client import start_http_server

from app.infra.db.session import get_async_session_local
from app.infra.telemetry import configure_telemetry
from app.kernel.events.dispatcher import OutboxDispatcherService
from app.kernel.events.retention import OutboxRetentionService
from app.kernel.observe.logging import setup_logging
from app.modules.knowledge.runtime.ingest_worker import GlobalKnowledgeIngestWorker
from app.modules.plugin.runtime.loader import PluginRuntimeLoader
from app.settings.settings import settings
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers
from app.wiring.schedule_worker import ScheduleWorker

logger = logging.getLogger(__name__)


async def main() -> None:
    """Start the ingest, outbox and schedule loops side by side."""
    setup_logging()
    settings.validate_runtime_requirements()
    configure_telemetry(service_name="soit-worker")
    PluginRuntimeLoader().load_all()
    register_outbox_handlers()
    metrics_port = max(1, int(settings.outbox_dispatcher_metrics_port))
    start_http_server(metrics_port, addr="0.0.0.0")

    session_local = get_async_session_local()
    dispatcher = OutboxDispatcherService(
        get_outbox_registry(),
        db_factory=session_local,
        batch_limit=max(1, int(settings.outbox_dispatcher_batch_limit)),
        max_dispatch_attempts=max(1, int(settings.outbox_dispatcher_max_attempts)),
        lease_seconds=max(1, int(settings.outbox_dispatcher_lease_seconds)),
    )
    retention = OutboxRetentionService(
        session_local,
        retention_days=int(settings.outbox_retention_days),
        batch_size=int(settings.outbox_retention_batch_size),
    )
    ingest = GlobalKnowledgeIngestWorker()
    scheduler = ScheduleWorker(
        lambda: session_local(),
        lease_seconds=int(settings.schedule_worker_lease_seconds),
    )
    logger.info(
        "Starting combined worker",
        extra={"worker_id": dispatcher.worker_id, "metrics_port": metrics_port},
    )
    await asyncio.gather(
        dispatcher.run_loop(
            poll_interval_seconds=max(0.05, float(settings.outbox_dispatcher_poll_interval))
        ),
        retention.run_loop(interval_seconds=float(settings.outbox_retention_interval_seconds)),
        ingest.run_loop(
            poll_interval=max(0.1, settings.knowledge_ingest_worker_poll_interval),
            max_tasks=settings.knowledge_ingest_worker_max_tasks or None,
            concurrency=settings.knowledge_ingest_worker_concurrency,
            heartbeat_interval=settings.knowledge_ingest_worker_heartbeat_seconds,
        ),
        scheduler.run_loop(poll_interval=max(1.0, float(settings.schedule_worker_poll_interval))),
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        # psycopg's async driver refuses the Proactor loop (see serve_dev.py).
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
