"""ingest_worker

Run dataset ingest worker loop.
"""

import asyncio

from app.settings.settings import settings
from app.modules.dataset.runtime.ingest_worker import GlobalDatasetIngestWorker


async def main() -> None:
    """Start dataset ingest worker."""
    import logging
    logging.basicConfig(level=settings.log_level or "INFO")
    print(
        f"Starting ingest worker: poll_interval={max(0.1, settings.dataset_ingest_worker_poll_interval)} "
        f"max_tasks={settings.dataset_ingest_worker_max_tasks} "
        f"concurrency={settings.dataset_ingest_worker_concurrency} "
        f"heartbeat={settings.dataset_ingest_worker_heartbeat_seconds}",
        flush=True,
    )
    logging.getLogger(__name__).info(
        "Starting ingest worker: poll_interval=%s max_tasks=%s concurrency=%s heartbeat=%s",
        max(0.1, settings.dataset_ingest_worker_poll_interval),
        settings.dataset_ingest_worker_max_tasks,
        settings.dataset_ingest_worker_concurrency,
        settings.dataset_ingest_worker_heartbeat_seconds,
    )
    worker = GlobalDatasetIngestWorker()
    await worker.run_loop(
        poll_interval=max(0.1, settings.dataset_ingest_worker_poll_interval),
        max_tasks=settings.dataset_ingest_worker_max_tasks,
        concurrency=settings.dataset_ingest_worker_concurrency,
        heartbeat_interval=settings.dataset_ingest_worker_heartbeat_seconds,
    )


if __name__ == "__main__":
    asyncio.run(main())
