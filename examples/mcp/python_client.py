"""List a SOIT workspace's tools over MCP and call one.

    pip install mcp
    SOIT_MCP_URL=http://localhost:9200/mcp SOIT_API_KEY=sk_... python python_client.py
"""

from __future__ import annotations

import asyncio
import os

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    url = os.environ.get("SOIT_MCP_URL", "http://localhost:9200/mcp")
    headers = {"Authorization": f"Bearer {os.environ['SOIT_API_KEY']}"}
    async with httpx.AsyncClient(headers=headers, timeout=60) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                info = await session.initialize()
                print(f"connected to {info.serverInfo.name} {info.serverInfo.version}")

                for tool in (await session.list_tools()).tools:
                    print(f"- {tool.name}: {tool.description}")

                result = await session.call_tool("function_time_now", {})
                # SOIT names the run each call became, to find it in Observe > Runs.
                print("run:", (result.meta or {}).get("ai.soit/run_id"))
                print(result.structuredContent or result.content)


if __name__ == "__main__":
    asyncio.run(main())
