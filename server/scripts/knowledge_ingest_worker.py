"""knowledge_ingest_worker

Run knowledge ingestion tasks in the background for a specific tenant/workspace.

Usage:
    python scripts/knowledge_ingest_worker.py --tenant-id t1 --workspace-id w1
    python scripts/knowledge_ingest_worker.py --tenant-id t1 --workspace-id w1 --once
"""

from __future__ import annotations

import argparse
import asyncio

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db_sync
from app.wiring.services import build_knowledge_service
from app.modules.knowledge.runtime.ingest_worker import KnowledgeIngestWorker


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run knowledge ingestion worker.")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID to process.")
    parser.add_argument("--workspace-id", required=True, help="Workspace ID to process.")
    parser.add_argument("--user-id", default="system", help="User ID for worker context.")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Polling interval in seconds.")
    parser.add_argument("--max-tasks", type=int, default=None, help="Max tasks before exit.")
    parser.add_argument("--once", action="store_true", help="Process at most one task then exit.")
    return parser.parse_args()


async def _run_worker(args: argparse.Namespace) -> int:
    db = get_db_sync()
    try:
        ctx = RequestContext(
            tenant_id=args.tenant_id,
            workspace_id=args.workspace_id,
            user_id=args.user_id,
            tenant_role="Owner",
            workspace_role="Owner",
        )
        service = build_knowledge_service(db=db, ctx=ctx)
        worker = KnowledgeIngestWorker(service)

        if args.once:
            task = await worker.run_once()
            return 1 if task else 0

        return await worker.run_loop(
            poll_interval=max(0.1, args.poll_interval),
            max_tasks=args.max_tasks,
        )
    finally:
        db.close()


def main() -> int:
    args = _parse_args()
    processed = asyncio.run(_run_worker(args))
    print(f"Processed tasks: {processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
