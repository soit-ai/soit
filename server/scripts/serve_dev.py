"""Run the API on an event loop that psycopg's async driver accepts.

On Windows, uvicorn 0.36+ builds a ``ProactorEventLoop`` unless it spawns
subprocesses (``--reload`` / ``--workers``), and psycopg refuses to run async
on it. This launcher installs the selector policy first and serves inside that
loop. Linux and containers do not need it; use ``uvicorn app.main:app`` there.

    uv run python scripts/serve_dev.py --port 9200
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9200)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = uvicorn.Config(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )
    asyncio.run(uvicorn.Server(config).serve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
