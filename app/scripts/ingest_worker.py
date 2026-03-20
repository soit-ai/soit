"""ingest_worker

Run knowledge ingest worker loop.
"""

import asyncio

from app.settings.settings import settings
from app.modules.knowledge.runtime.ingest_worker import GlobalKnowledgeIngestWorker


async def main() -> None:
    """Start knowledge ingest worker."""
    import logging
    logging.basicConfig(level=settings.log_level or "INFO")
    print(
        f"Starting ingest worker: poll_interval={max(0.1, settings.knowledge_ingest_worker_poll_interval)} "
        f"max_tasks={settings.knowledge_ingest_worker_max_tasks} "
        f"concurrency={settings.knowledge_ingest_worker_concurrency} "
        f"heartbeat={settings.knowledge_ingest_worker_heartbeat_seconds}",
        flush=True,
    )
    logging.getLogger(__name__).info(
        "Starting ingest worker: poll_interval=%s max_tasks=%s concurrency=%s heartbeat=%s",
        max(0.1, settings.knowledge_ingest_worker_poll_interval),
        settings.knowledge_ingest_worker_max_tasks,
        settings.knowledge_ingest_worker_concurrency,
        settings.knowledge_ingest_worker_heartbeat_seconds,
    )
    worker = GlobalKnowledgeIngestWorker()
    await worker.run_loop(
        poll_interval=max(0.1, settings.knowledge_ingest_worker_poll_interval),
        max_tasks=settings.knowledge_ingest_worker_max_tasks,
        concurrency=settings.knowledge_ingest_worker_concurrency,
        heartbeat_interval=settings.knowledge_ingest_worker_heartbeat_seconds,
    )


if __name__ == "__main__":
    asyncio.run(main())
