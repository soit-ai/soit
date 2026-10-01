"""Call SOIT's Anthropic-compatible gateway with the Anthropic Python SDK.

    pip install anthropic
    export SOIT_BASE_URL=http://localhost:9200/v1
    export SOIT_API_KEY=sk_...                      # Settings > API
    export SOIT_MODEL=model:openai-main:gpt-5.5     # from GET /v1/models
    python python_anthropic.py

The model behind the call does not have to be Anthropic's: SOIT translates the
Messages request for whichever provider the model ref names.
"""

from __future__ import annotations

import os

from anthropic import Anthropic

# The Anthropic SDK adds /v1/messages itself, so its base URL has no /v1.
client = Anthropic(
    base_url=os.environ.get("SOIT_BASE_URL", "http://localhost:9200/v1").removesuffix("/v1"),
    api_key=os.environ["SOIT_API_KEY"],
)
model = os.environ["SOIT_MODEL"]

print("models:", [item.id for item in client.models.list()])

# Every call is a governed run; the raw response carries its id.
raw = client.messages.with_raw_response.create(
    model=model,
    max_tokens=256,
    messages=[{"role": "user", "content": "Say hello in five words."}],
)
message = raw.parse()
print("run:", raw.headers.get("x-soit-run-id"))
print("reply:", message.content[0].text)  # type: ignore[union-attr]
print("usage:", message.usage.input_tokens, message.usage.output_tokens)

with client.messages.stream(
    model=model,
    max_tokens=256,
    messages=[{"role": "user", "content": "Count to five."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    print()

# A client-defined tool: the model asks for it, the caller runs it.
reply = client.messages.create(
    model=model,
    max_tokens=256,
    messages=[{"role": "user", "content": "What is the weather in Paris?"}],
    tools=[
        {
            "name": "get_weather",
            "description": "Current weather for a city",
            "input_schema": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
    ],
)
for block in reply.content:
    if block.type == "tool_use":
        print("tool call:", block.name, block.input)
