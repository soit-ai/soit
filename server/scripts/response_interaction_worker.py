"""Run the durable response interaction worker as a dedicated process.

The API process hosts the same loop by default; this entrypoint is for
deployments that set RESPONSE_INTERACTION_WORKER_IN_API=false on the API so
model-bound executions stop sharing CPU with request handling.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from prometheus_client import start_http_server

from app.infra.telemetry import configure_telemetry
from app.kernel.observe.logging import setup_logging
from app.modules.plugin.runtime.loader import PluginRuntimeLoader
from app.settings.settings import settings
from app.wiring.response_interaction_worker import (
    GlobalResponseInteractionWorker,
    bounded_concurrency,
)
from app.wiring.task_drivers import register_task_drivers

logger = logging.getLogger(__name__)


async def main() -> None:
    """Validate dependencies, load plugins, and start claiming interactions."""
    setup_logging()
    settings.validate_runtime_requirements()
    if not settings.response_interaction_worker_enabled:
        raise RuntimeError("RESPONSE_INTERACTION_WORKER_ENABLED must be true for the worker process")
    configure_telemetry(service_name="soit-response-worker")
    # Agent executions call plugin tools and task drivers, both registered
    # at API startup; the worker needs the same registries.
    PluginRuntimeLoader().load_all()
    register_task_drivers()
    metrics_port = max(1, int(settings.response_interaction_worker_metrics_port))
    start_http_server(metrics_port, addr="0.0.0.0")
    worker = GlobalResponseInteractionWorker()
    concurrency = bounded_concurrency(settings.response_interaction_worker_concurrency)
    logger.info(
        "Starting dedicated response interaction worker",
        extra={
            "worker_id": worker.worker_id,
            "concurrency": concurrency,
            "lease_seconds": worker.lease_seconds,
            "metrics_port": metrics_port,
        },
    )
    await worker.run_loop(
        poll_interval=max(0.05, float(settings.response_interaction_worker_poll_interval)),
        concurrency=concurrency,
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        # psycopg's async driver refuses the Proactor loop (see serve_dev.py).
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
