"""Run an OpenAI Agents SDK agent on SOIT's OpenAI-compatible gateway.

SOIT serves Chat Completions, not the Responses API, so the agent uses the
SDK's chat-completions model with a client pointed at SOIT. Tracing to
OpenAI is switched off: SOIT records every call as a governed run.

    pip install openai-agents
    export SOIT_BASE_URL=http://localhost:9200/v1
    export SOIT_API_KEY=sk_...                      # Settings > API
    export SOIT_MODEL=model:openai-main:gpt-5.5     # from GET /v1/models
    python openai_agents.py
"""

from __future__ import annotations

import asyncio
import os

from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from openai import AsyncOpenAI

set_tracing_disabled(True)

soit = AsyncOpenAI(
    base_url=os.environ.get("SOIT_BASE_URL", "http://localhost:9200/v1"),
    api_key=os.environ["SOIT_API_KEY"],
)


@function_tool
def get_weather(city: str) -> str:
    """Current weather for a city."""
    return f"Sunny, 24 C in {city}"


agent = Agent(
    name="Travel helper",
    instructions="Answer briefly. Use tools for facts you do not know.",
    model=OpenAIChatCompletionsModel(model=os.environ["SOIT_MODEL"], openai_client=soit),
    tools=[get_weather],
)


async def main() -> None:
    result = await Runner.run(agent, "Should I pack sunglasses for Lisbon today?")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
