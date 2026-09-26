"""Use SOIT's OpenAI-compatible gateway as a LangChain chat model.

    pip install langchain-openai
    export SOIT_BASE_URL=http://localhost:9200/v1
    export SOIT_API_KEY=sk_...                      # Settings > API
    export SOIT_MODEL=model:openai-main:gpt-5.5     # from GET /v1/models
    python langchain_chat.py
"""

from __future__ import annotations

import os

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url=os.environ.get("SOIT_BASE_URL", "http://localhost:9200/v1"),
    api_key=os.environ["SOIT_API_KEY"],
    model=os.environ["SOIT_MODEL"],
    # SOIT answers one choice per call; usage arrives on the last chunk.
    n=1,
    stream_usage=True,
)

print(llm.invoke("Say hello in five words.").content)

for chunk in llm.stream("Count to five."):
    print(chunk.content, end="", flush=True)
print()


@tool
def get_weather(city: str) -> str:
    """Current weather for a city."""
    return f"Sunny, 24 C in {city}"


reply = llm.bind_tools([get_weather]).invoke("What is the weather in Lisbon?")
for call in reply.tool_calls:
    print("tool call:", call["name"], call["args"], "->", get_weather.invoke(call["args"]))
