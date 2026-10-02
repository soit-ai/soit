# Calling SOIT through the OpenAI-compatible gateway

SOIT serves an OpenAI-compatible API under `/v1`. Point an OpenAI client at
it with a SOIT API key and every call becomes a governed run: rate limits,
quotas, budgets, content safety, cost and audit apply as they do to SOIT's own
agents. The run id comes back in the `x-soit-run-id` response header.

| Setting  | Value |
| -------- | ----- |
| Base URL | your SOIT API address plus `/v1`, e.g. `http://localhost:9200/v1` |
| API key  | a SOIT API key from **Settings › API** (`sk_…`), sent as `Authorization: Bearer` |
| Model    | a model ref as `GET /v1/models` lists it, e.g. `model:openai-main:gpt-5.5`, or a virtual model, `vmodel:{slug}` |

Every example reads the same three environment variables:

```bash
export SOIT_BASE_URL=http://localhost:9200/v1
export SOIT_API_KEY=sk_...
export SOIT_MODEL=model:openai-main:gpt-5.5
```

| File | Client | Needs |
| ---- | ------ | ----- |
| [`curl.sh`](curl.sh) | curl | curl, jq |
| [`python_openai.py`](python_openai.py) | OpenAI Python SDK | `pip install openai` |
| [`node_openai.mjs`](node_openai.mjs) | OpenAI Node SDK | `npm install openai` |
| [`langchain_chat.py`](langchain_chat.py) | LangChain `ChatOpenAI` | `pip install langchain-openai` |
| [`openai_agents.py`](openai_agents.py) | OpenAI Agents SDK | `pip install openai-agents` |
| [`python_anthropic.py`](python_anthropic.py) | Anthropic Python SDK | `pip install anthropic` |
| [`claude_code.md`](claude_code.md) | Claude Code | the `claude` CLI |
| [`tools.sh`](tools.sh) | curl, SOIT tools API | curl, jq |

To stand up and accept a whole pilot (provider, failover, key, budget and the
checks that show they govern the calls), see the [pilot kit](../pilot/README.md).

## Served endpoints

- `POST /v1/chat/completions`: whole or streamed, with tools, images in
  messages and structured output (`response_format`).
- `GET /v1/models`: the models and virtual models the key may call.
- `POST /v1/messages` and `POST /v1/messages/count_tokens`: the Anthropic
  Messages API, for the Anthropic SDKs and Claude Code. Its base URL has no
  `/v1`, its key goes in `x-api-key`, and refusals use Anthropic's error body.
- `POST /v1/embeddings`: float or base64 vectors.
- `POST /v1/images/generations` and `POST /v1/images/edits`.

The Responses API (`/v1/responses`), Assistants, files, audio, batch and
fine-tuning endpoints are not served. The OpenAI Agents SDK therefore uses its
chat-completions model, as `openai_agents.py` shows.

## What differs from OpenAI

- `n` must be 1, so each choice stays one governed call.
- Image parameters SOIT does not send (`quality`, `style`, `moderation`,
  `output_compression`, `input_fidelity`, `partial_images`, `stream`) are
  refused with `400` unless they carry OpenAI's default, rather than ignored.
  An image option the model's route cannot carry, such as a `webp` edit on
  OpenAI, is refused with `422` (`UnprocessableEntityError` in the SDK).
- A model is named by its SOIT ref, not the provider's bare model name.
- Refusals use OpenAI's error shape with SOIT's reasons: `402`
  (`insufficient_quota`, code `budget_exhausted`) when a budget with a hard
  stop is spent; `403` (`permission_error`) for a model or address the key
  may not use; `429` (`rate_limit_error`) with `Retry-After` for a rate limit
  or quota.
- A stream that fails part way ends with an error event, and a stream the
  client abandons is recorded as `CLIENT_DISCONNECTED`.

## How these are tested

`server/tests/compat` drives the official Anthropic Python SDK against
`/v1/messages` and the OpenAI Python SDK against the rest of the gateway in CI.
The OpenAI suite covers
completions, streams, tool calls, structured output, embeddings, model
listing, image generation and edits, and error classes. LangChain's
`ChatOpenAI` and the Agents SDK's chat-completions model call through that
same client, so the request shapes they send are part of that suite.
