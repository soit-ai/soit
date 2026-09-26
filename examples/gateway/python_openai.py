"""Call SOIT's OpenAI-compatible gateway with the OpenAI Python SDK.

    pip install openai
    export SOIT_BASE_URL=http://localhost:9200/v1
    export SOIT_API_KEY=sk_...                      # Settings > API
    export SOIT_MODEL=model:openai-main:gpt-5.5     # from GET /v1/models
    python python_openai.py
"""

from __future__ import annotations

import json
import os

from openai import OpenAI

client = OpenAI(
    base_url=os.environ.get("SOIT_BASE_URL", "http://localhost:9200/v1"),
    api_key=os.environ["SOIT_API_KEY"],
)
model = os.environ["SOIT_MODEL"]

print("models:", [item.id for item in client.models.list()])

# Every call is a governed run; the raw response carries its id.
raw = client.chat.completions.with_raw_response.create(
    model=model,
    messages=[{"role": "user", "content": "Say hello in five words."}],
)
completion = raw.parse()
print("run:", raw.headers.get("x-soit-run-id"))
print("reply:", completion.choices[0].message.content)

stream = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Count to five."}],
    stream=True,
    stream_options={"include_usage": True},
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
    if chunk.usage:
        print(f"\ntokens: {chunk.usage.total_tokens}")

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]
messages = [{"role": "user", "content": "What is the weather in Lisbon?"}]
first = client.chat.completions.create(model=model, messages=messages, tools=tools)
message = first.choices[0].message
if message.tool_calls:
    messages.append(message.model_dump(exclude_none=True))
    for call in message.tool_calls:
        city = json.loads(call.function.arguments).get("city")
        messages.append(
            {"role": "tool", "tool_call_id": call.id, "content": f"Sunny, 24 C in {city}"}
        )
    final = client.chat.completions.create(model=model, messages=messages, tools=tools)
    print("with tools:", final.choices[0].message.content)
