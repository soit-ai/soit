"""Run the transactional outbox dispatcher as a dedicated process."""

from __future__ import annotations

import asyncio
import logging

from prometheus_client import start_http_server

from app.infra.db.session import get_db_sync
from app.infra.telemetry import configure_telemetry
from app.kernel.events.dispatcher import OutboxDispatcherService
from app.kernel.observe.logging import setup_logging
from app.modules.plugin.runtime.loader import PluginRuntimeLoader
from app.settings.settings import settings
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers

logger = logging.getLogger(__name__)


async def main() -> None:
    """Validate dependencies, register consumers, and start polling."""
    setup_logging()
    settings.validate_runtime_requirements()
    configure_telemetry(service_name="soit-outbox-dispatcher")
    PluginRuntimeLoader().load_all()
    register_outbox_handlers()
    metrics_port = max(1, int(settings.outbox_dispatcher_metrics_port))
    start_http_server(metrics_port, addr="0.0.0.0")
    service = OutboxDispatcherService(
        get_outbox_registry(),
        db_factory=get_db_sync,
        batch_limit=max(1, int(settings.outbox_dispatcher_batch_limit)),
        max_dispatch_attempts=max(1, int(settings.outbox_dispatcher_max_attempts)),
        lease_seconds=max(1, int(settings.outbox_dispatcher_lease_seconds)),
    )
    logger.info(
        "Starting dedicated outbox dispatcher",
        extra={
            "worker_id": service.worker_id,
            "batch_limit": service.batch_limit,
            "lease_seconds": service.lease_seconds,
            "metrics_port": metrics_port,
        },
    )
    await service.run_loop(
        poll_interval_seconds=max(0.05, float(settings.outbox_dispatcher_poll_interval))
    )


if __name__ == "__main__":
    asyncio.run(main())
