# OpenAI-compatible gateway

SOIT serves an OpenAI-compatible API under `/v1`, next to its own API under
`/api/v1`. Any client built for OpenAI (the official SDKs, LangChain, the
OpenAI Agents SDK, most tools that accept a base URL) can call the models a
workspace has configured, and every call is governed the way SOIT's own
agents are: rate limits, quotas, budgets, content safety, cost recording and
audit.

Anthropic clients work too: `POST /v1/messages` serves the Messages API (see
[Anthropic Messages](#anthropic-messages)), so Claude Code and the Anthropic
SDKs can be pointed at SOIT the same way.

The same keys also call the workspace's tools by reference, under
`/api/v1/tools` (see [Calling tools](#calling-tools)).

Examples for curl, Python, Node, LangChain and the Agents SDK are in
[`examples/gateway/`](../examples/gateway/).

## Connecting

| Setting  | Value |
| -------- | ----- |
| Base URL | the API address plus `/v1`, e.g. `http://localhost:9200/v1` |
| API key  | a SOIT API key, sent as `Authorization: Bearer sk_…` |
| Model    | a model ref, `model:{provider}:{model}`, or a virtual model, `vmodel:{slug}` |

`GET /v1/models` lists what the key may call, by the name a call uses. Each
entry carries OpenAI's fields and Anthropic's (`type`, `display_name`,
`created_at`), and the list `has_more`, `first_id` and `last_id`, so the SDKs
of either parse it.

Create keys under **Settings › API** or with `POST /api/v1/api-keys`. A key
carries scopes (`read`, `write`, `admin`) that cap what it may do below its
owner's role; calling models needs `write`. A key is shown once, at creation
or rotation.

## Endpoints

| Endpoint | Notes |
| -------- | ----- |
| `POST /v1/chat/completions` | Whole or streamed (`stream`, `stream_options.include_usage`). Tools and `tool_choice`, images in user messages, `response_format` (`json_object`, `json_schema`), `temperature`, `top_p`, `max_tokens` / `max_completion_tokens`, `stop`, `seed`. `n` must be 1. |
| `GET /v1/models` | Active models and virtual models the key may call. |
| `POST /v1/embeddings` | `encoding_format` `float` or `base64` (the SDKs' default). |
| `POST /v1/images/generations` | `n`, `size` (64 to 4096 pixels a side, or `auto`), `response_format`, `background`, `output_format` (`png`, `jpeg`, `webp`), `quality`. `background: auto` is the provider's default and is not sent; a transparent background with `jpeg` is refused. `quality` is sent as given (gpt-image reads `low`, `medium`, `high`; DALL-E 3 `hd`), except `auto` and `standard`, which leave the choice to the provider and are not sent; it must be a lowercase word. `style`, `moderation`, `output_compression`, `partial_images` and `stream` are not sent: their defaults (`style` `vivid`, `moderation` `auto`, `output_compression` `100`, `partial_images` `0`, `stream` `false`) are accepted, and any other value is refused with `400` naming the parameter. |
| `POST /v1/images/edits` | Multipart `image` and optional `mask`. As in OpenAI's API, the mask's transparent pixels mark the area to edit. Takes the same `n`, `size`, `response_format`, `background`, `output_format` and `quality` as generations. Whether each reaches the provider depends on the model's route; see [Image options by route](#image-options-by-route). `input_fidelity`, `output_compression`, `partial_images` and `stream` are treated as on generations (`input_fidelity`'s default is `low`). |

Fields SOIT does not know are ignored rather than refused, so clients that
send parameters newer than SOIT, or vendor extensions, keep working. OpenAI
image parameters SOIT knows but does not send are the exception: ignoring
one would return and bill an image other than the one asked for, so a value
other than its default is refused. An OpenAI image parameter SOIT starts
modelling is announced in the changelog, since from then on a value it
ignored is refused or sent. `user` is accepted and not sent. The Responses
API (`/v1/responses`), Assistants, files, audio, batch and fine-tuning are
not served.

On models reached through OpenAI's Responses API (the GPT-5.5 family on an
`openai` provider), `stop` is refused because that API cannot honour it, and
`seed` is not sent.

## Anthropic Messages

`POST /v1/messages` answers the Anthropic Messages API, so Claude Code, the
Anthropic SDKs and other tools built for it can call the workspace's models
through the same governed path as `/v1/chat/completions`: one run per call
(`source=gateway`), the same rate limits, quotas, budgets, content safety and
cost ledger. The model behind a call does not have to be Anthropic's: SOIT
translates the request for whichever provider the model ref names.

| Setting  | Value |
| -------- | ----- |
| Base URL | the API address with no `/v1` (the SDKs add `/v1/messages`), e.g. `http://localhost:9200` |
| API key  | a SOIT API key, sent as `x-api-key: sk_…` or `Authorization: Bearer sk_…` |
| Model    | a model ref, `model:{provider}:{model}`, or a virtual model, `vmodel:{slug}` |

```bash
export ANTHROPIC_BASE_URL=http://localhost:9200
export ANTHROPIC_API_KEY=sk_…
export ANTHROPIC_MODEL=model:anthropic:claude-sonnet-5-5   # Claude Code
```

| Request field | Behaviour |
| ------------- | --------- |
| `model`, `max_tokens`, `messages` | Required. Content is a string or blocks: `text`, `image` (`base64` or `url` source), `tool_use` and `tool_result` (text content). |
| `system` | A string or `text` blocks, joined into one system message. |
| `temperature`, `top_p`, `stop_sequences`, `stream` | Sent to the model. |
| `tools`, `tool_choice` | Client-defined tools. `tool_choice` `auto`, `any`, `tool` and `none` are honoured; `disable_parallel_tool_use` is accepted and not sent. |
| `top_k`, `metadata`, `service_tier`, `thinking`, `cache_control` | Accepted and not sent. Responses never carry thinking blocks, and thinking blocks in the history are dropped. |
| `anthropic-version`, `anthropic-beta` headers | Accepted and not interpreted. |

Anything SOIT cannot carry is refused with `400` naming it rather than
ignored: a `document` or other content block, an image inside a `tool_result`,
and tools Anthropic runs itself (web search, code execution, bash, the text
editor, computer use), since dropping one would change what the model can do
without saying so.

A streamed call uses Anthropic's named events (`message_start`, `ping`,
`content_block_start`, `content_block_delta`, `content_block_stop`,
`message_delta`, `message_stop`). `message_start` carries SOIT's estimate of the
prompt's tokens, and `message_delta` the provider's count once it is known. The
gateway's outbound content check can hold text back, so a streamed reply may
deliver its tool calls before its text. `stop_reason` follows what the provider
reports (`end_turn`, `max_tokens`, `tool_use`, `stop_sequence`, `refusal`); a
provider that reports a bare stop does not say whether a stop sequence ended
the turn, so that case is `end_turn`, and `stop_sequence` is always `null`.

`POST /v1/messages/count_tokens` returns `{"input_tokens": n}` for a prompt. It
is SOIT's estimate, not the provider's tokenizer, calls no model, opens no run
and is not billed. The Message Batches and Files APIs are not served; `GET /v1/models` answers the Models API's list.

## Image options by route

Image calls, through `/v1/images` and `/api/v1/images` alike, go through
LiteLLM, whose request for each provider has a place for some options and
not others. SOIT records which of `background`, `output_format`, `quality`,
`seed`, `strength`, `negative_prompt`, `mask`, `size`, `response_format` and
more than one image (`n` above 1) each LiteLLM image route carries, and CI checks
the record against the requests LiteLLM sends. An option counts as carried
where LiteLLM maps it to a field of the provider's API or, for a provider
that takes OpenAI's image request, sends it under OpenAI's name.

An option the model's route does not carry is refused with `422`
`MODEL_IMAGE_CAPABILITY_UNAVAILABLE` before a run opens, for an asynchronous
job as for a synchronous call, and nothing is admitted or billed. On `/v1`
the error names the option in `param`. On `/api/v1`, `details` names it in
`param` and `capability`, gives `reason` `route_cannot_carry`, and `route`,
LiteLLM's name for the route, which may change with LiteLLM; a refused `n`
adds `max_n`. A refusal because the model declared a trait in
`capabilities_json.image` says `reason` `declared`; declaring a trait, such
as `supports_seed: true`, cannot make a route carry an option.
`response_format` is the exception: see below.

Two values ask for nothing a route could drop, and are accepted and not sent
where it has no place for them: `size` `auto`, which leaves the size to the
provider and is sent only where the route reads OpenAI's sizes, and
`output_format` `png`. The provider then answers in its own format, PNG on
most routes but JPEG on several fal models, and a stored image is typed
from its bytes.

`response_format` is sent where the route takes it, and not to the
gpt-image and chatgpt-image families, which refuse it; a `url` that cannot
then be promised is refused with `400` `VALIDATION_ERROR`. A model's
declared `capabilities_json.image.response_format_param` overrides both:
`true` sends it, `false` does not.

A provider's row is decided by the provider LiteLLM resolves for the model:
its `litellm_provider`, or else its kind's preset, so a provider of kind
`openai_compatible` uses the OpenAI row whatever model it serves. LiteLLM
moves an Azure AI model it knows as an OpenAI image model, such as
`gpt-image-1` or `dall-e-3`, to the Azure OpenAI row, edits included. A
DALL-E entry applies to a model or deployment whose name contains `dall-e-2`
or `dall-e-3` (on Azure, with or without the hyphens), which is how LiteLLM tells them
from gpt-image.

| Route | Generation carries | Edit carries |
| ----- | ------------------ | ------------ |
| OpenAI, Azure OpenAI | `background`, `output_format`, `quality`, `n`, `size`; DALL-E also `response_format` | `background`, `quality`, `n`, `mask`, `size`, `response_format` |
| LiteLLM proxy | `background`, `output_format`, `quality`, `n`, `size` | `background`, `quality`, `n`, `mask`, `size`, `response_format` |
| Azure AI gpt-image and DALL-E deployments under other names | `background`, `output_format`, `quality`, `n`, `size`; DALL-E also `response_format` | not supported by LiteLLM |
| Azure AI FLUX 1 / FLUX 2 / MAI | FLUX 1: `background`, `output_format`, `quality`, `n`, `size`; FLUX 2: none; MAI: `size` | FLUX 1: `background`, `quality`, `n`, `mask`, `size`, `response_format`; FLUX 2 and MAI: `n`, `size` |
| Providers LiteLLM treats as OpenAI-compatible without an image config of their own (Volcengine, vLLM, Together), Xinference, CometAPI, ModelScope | `background`, `output_format`, `quality`, `n`, `size`, `response_format` | not supported by LiteLLM |
| Recraft | `background`, `output_format`, `n`, `size`, `response_format` | `n`, `response_format` |
| Gemini: Imagen / image models | Imagen: `background`, `output_format`, `n`, `size`; image models: `n`, `size` | Imagen: `n`; image models: `n`, `size` |
| Vertex AI: Imagen / Gemini image models | `n`, `size` | Imagen: `n`, `mask`; Gemini: `size` |
| OpenRouter | `size` | `n`, `size` |
| DashScope | `n`, `size` | not supported by LiteLLM |
| Bedrock | SDXL: `size`; SD3 and Stable Image: none; Titan and Nova Canvas: `n`, `size` | Nova Canvas: `quality`, `seed`, `n`, `mask`, `size`; Stability edit models (inpaint, outpaint, search-and-replace and the like): `output_format`, `seed`, `strength`, `negative_prompt`, `mask`, `size`; SDXL, SD3, Stable Image and Titan: not supported by LiteLLM |
| Stability | `output_format`, `size` | `seed`, `strength`, `negative_prompt`, `mask`, `size` |
| Black Forest Labs | `size`; ultra models also `n` | `output_format`, `seed`; no mask |
| fal | `n`, `size` for Imagen 4, Nano Banana, FLUX Pro 1.1 and Ultra, FLUX Schnell, Seedream, Dreamina, Ideogram and Stable Diffusion; `size` for Recraft V3 and Bria; none for other models | not supported by LiteLLM |
| AI/ML API, RunwayML | AI/ML API: `n`, `size`, `response_format`; RunwayML: `size` | not supported by LiteLLM |

A route LiteLLM cannot generate or edit with at all, or a provider on the
native adapter, which serves no images, is refused as a missing capability
(`MODEL_CAPABILITY_UNAVAILABLE`, `reason` `no_litellm_route` or
`native_adapter`) when the route is chosen, so a virtual model moves on to
its next target. An option a target's route cannot carry, or a trait it
declared it lacks, also moves a virtual model on to its next target, before
anything is billed; the last target's refusal is the one the caller gets,
and each passed-over target is recorded on the run step as an attempt with
the option in `param`. A provider's `drop_params` setting no longer decides what
an image provider receives: what a route cannot carry is refused either
way, and Bedrock's SDXL and SD3 generations, Black Forest Labs edits and
Vertex AI Gemini edits no longer need it.

## Every call is a run

Each call creates a run with `mode=gateway`, `kind` `chat`, `embedding` or
`image`, and `source=gateway`. Its subject is the API key, or the user when a
signed-in session calls. The run id comes back in the `x-soit-run-id` header
and is the id of a chat completion (`chatcmpl-{run id}`).

The run records its model step, tokens, latency and cost, like any other run.
**Observe › Runs** filters by entry and by key (`source`, `api_key_id` on
`GET /api/v1/runs` and on every cost breakdown under `/api/v1/runs/costs`),
and **Settings › API** links each key to its runs. Daily usage aggregates sum
calls, tokens and priced amount per day, entry, user or service principal,
key, provider, model and operation.

## Calling tools

The same keys call the workspace's tools directly, with no agent in between:

| Endpoint | Notes |
| -------- | ----- |
| `GET /api/v1/tools` | The tools the key may invoke: built-ins, installed plugin tools and the tools of enabled MCP servers, each with the schema of its arguments and whether it needs approval. |
| `GET /api/v1/tools/{ref}` | One tool. |
| `POST /api/v1/tools/{ref}/invoke` | `{"arguments": {...}}`, and optionally an `Idempotency-Key` header. |

A call goes through the tool gateway SOIT's agents use: secrets referenced as
`{"secret_id": "..."}` are injected there and never returned; egress policy,
rate limits and budgets apply; the call is audited and costed. It is a run
with `mode=tool` and `source=gateway`, named in `x-soit-run-id`, which
**Observe › Runs** shows, replays and exports like any other run, evidence
bundle included.

These endpoints answer in SOIT's envelope, `{"success": true, "data": {...}}`,
not OpenAI's. `data` carries `run_id`, `status` (`succeeded`, `failed`,
`waiting_approval` or `rejected`), `result` or `error`, `idempotency_key` and
`replayed`. A tool that ran and failed is `200` with `status: failed`; a call
SOIT refused is an error: `400` for arguments that do not match the tool's
schema, `403` for a tool or address the key may not use, `404` for an unknown
tool, `409` for a reused key.

**Idempotency.** With an `Idempotency-Key`, a call is safe to retry: the same
key returns the recorded outcome (`replayed: true`) without calling the tool
again, and the same key with another tool or other arguments is `409`. Keys
belong to the caller, so two API keys never share one. Without a key, SOIT
assigns one and returns it in the `Idempotency-Key` response header.

**Pricing.** A tool that bills (a search API, a scraper, a paid data source)
declares what one call costs in its ToolSpec policy, and every successful
call is charged it, against budgets and credits, like a model call:

```json
"policy": {"audit_level": "basic", "pricing": {"currency": "USD", "call": "0.002"}}
```

The price is a decimal string with at most six decimal places; `"0"` is an
explicit free price. A call that is not charged still leaves a cost row,
unpriced, whose `pricing_snapshot.reason` says why:

| Reason | When |
| ------ | ---- |
| `tool_pricing_not_declared` | The tool declares no price. |
| `tool_call_failed` | The call failed; most failures never reach what the price bills. |
| `unsupported_pricing_config` | An MCP server's policy declares a price SOIT cannot read; a plugin ToolSpec with one is refused at install. |
| `tool_pricing_not_resolved` | A workflow called a tool of an enabled MCP server, whose price it does not look up yet. |

Calls through MCP `tools/call`, by agents and by workflows are priced the
same way.

**Approval.** A tool whose policy requires approval answers `202` with
`status: waiting_approval` and an `approval_id`, and the request appears in
**Govern › Approvals**. Once someone decides, send the same call with the same
key: an approved call runs and returns its result, a rejected one returns
`status: rejected` and never runs. Only the arguments that were put up for
approval can run.

```bash
curl -s "http://localhost:9200/api/v1/tools/tool:function:time_now/invoke" \
  -H "Authorization: Bearer $SOIT_API_KEY" \
  -H "Idempotency-Key: nightly-2026-09-27" \
  -H "Content-Type: application/json" \
  -d '{"arguments": {}}'
```

## What a key may do

Limits set on a key apply on top of its owner's own limits; an empty limit
means none of that kind. Set them in **Settings › API** or with
`PATCH /api/v1/api-keys/{key_id}`; rotation keeps them.

A key's calls are its model calls and its tool calls through `/api/v1/tools`
and `/mcp`, counted against one budget. Every tool request spends a call per
minute, a poll or a replay included; a tool call spends a call per 24 hours
once, when it starts, so running it once approved spends no more.

| Limit | Refusal |
| ----- | ------- |
| Calls per minute (model and tool calls) | `429`, `Retry-After` |
| Calls per 24 hours (model and tool calls) | `429`, `Retry-After` |
| Tokens per UTC day (model calls) | `429`, `Retry-After` |
| Allowed addresses (addresses or CIDR ranges) | `403` |
| Allowed models (`model:` and `vmodel:` refs) | `403`; `/v1/models` lists only these |
| Allowed tools (tool refs) | `403`; `/api/v1/tools` lists only these, and runs the key starts cannot call others either |
| Run content (`metadata_only`) | not a refusal: see below |

Behind a load balancer or reverse proxy, set `TRUSTED_PROXIES` (a JSON list
of addresses or CIDR ranges, e.g. `["10.0.0.0/8"]`). `X-Forwarded-For` is
believed only from those proxies, read from the right, so an allowlist sees
the real client rather than an address the client wrote.

## Service principals

A pipeline or partner system should not borrow a person's key. A service
principal is a non-human caller with a human owner and a workspace role
(`Viewer`, `Dev` or `Admin`), created by a workspace owner or admin under
**Settings › API** or with `POST /api/v1/service-principals`. A key issued to
it (`principal_id` on `POST /api/v1/api-keys`) authenticates as the
principal: runs, costs and audit are attributed to it. It acts only in its
own workspace, with the lower of its role and its owner's current role, and
stops working when the principal is disabled or the owner leaves.

## Budgets

A budget limits spend for the workspace, one key, one member or service
principal, or one agent, per UTC day or month, in one currency. Manage them
under **Govern › Budgets** or with `/api/v1/billing/budgets`;
`GET /api/v1/billing/budgets/statuses` reports every budget's spend,
remainder, percentage and forecast for the current period.

- A budget with a hard stop refuses model and tool calls once spent, with
  `402` (`insufficient_quota`, code `budget_exhausted`) naming the budget,
  what it spent and when it resets. The refusal is written to the audit
  ledger.
- Each admitted call holds its budgets for the period's average call cost
  until its cost is committed. Checking a budget and holding it are one step,
  so concurrent callers overshoot a limit by about one call at most. Holds
  live in Redis; while Redis is unreachable each process keeps its own.
- Crossing a threshold (50, 80 and 100 percent by default) notifies workspace
  owners and admins once per budget, period and threshold, in their inboxes,
  on their own endpoints as their preferences allow, and on the workspace's
  team channels subscribed to alerts.

## Content-free runs

When prompts and outputs must not be stored, set the workspace's
`content_capture` to `metadata_only` (**Settings › Security**), or ask for it
on one key. A key can tighten its workspace's mode but not loosen it. A
workspace admin may switch a workspace to `metadata_only`; only a tenant
admin may switch it back.

**Withheld.** The run records keep no content. Run and step summaries,
output previews and error text are stored as a length and a SHA-256 prefix.
The tool call in a step's metrics and gateway audit payloads keep their
structure and identifiers (runs, tool calls, child runs, secret references)
with every other value withheld the same way; the tool call ledger keeps the
argument names and whether a result came back; a URL keeps its origin. A
failed model or tool call's trace span names the failure without its text,
and a failed workflow node's event carries no error text. Statuses, error
codes, tokens, costs and timings are recorded as before, and callers still
get their answers, so `/v1`, `/api/v1/tools` and `/mcp` calls leave no
content behind.

**Still kept.** Some records hold content because the product needs it to
work: conversation threads, their messages and titles, responses and their
event streams, and task results, so a conversation can continue and an
asynchronous result can be fetched; approval requests, pending or decided,
so a reviewer sees what they approve; a workflow run's inputs, and until
it succeeds the outputs of its finished nodes, so it can resume or be
redriven; a task's checkpoint while it waits for approval; images an
`/api/v1/images` job returns as run artifacts; and what people write or
upload themselves: attachments, knowledge bases and memories.

**Effects.** Switching the mode does not rewrite what is already stored,
though an evidence bundle withholds it. A tool call whose tool answered,
with a result or an error of its own, has neither kept to hand back: sent
again with the same `Idempotency-Key` it is refused with `409`
`TOOL_RESULT_WITHHELD`, and a workflow node retried, resumed or redriven,
or an agent's tool call recovered after a crash, fails at that call
instead of replaying it. A call that failed before its tool answered
replays that failure, as it does when content is kept.
Retrying or replaying a run from its recorded input,
building a regression case from a run and searching runs by their text find
no text to work with. Logs and third-party instrumentation, such as HTTP
client spans that record outbound URLs, are outside this setting: keep them
under the same controls as the data.

## Virtual models

A virtual model is a workspace name, called as `vmodel:{slug}`, for an
ordered list of up to eight `model:` refs. Edit them under **Build › Models ›
Virtual models** or with `/api/v1/modelhub/virtual-models`.

A call tries the targets in order. A target that is unavailable (disabled,
removed, or missing a capability the call needs) is skipped, and so is a
target whose route cannot carry an image option the call asks for. A call that
fails with a timeout, `408`, `409`, `429`, a `5xx` or a lost connection moves
to the next target once that target's own retries are spent. An invalid
request or a policy refusal is not repeated elsewhere; a stream moves on only
before its first chunk; an image call is never repeated on another provider,
because the failed one may have billed it. Each attempt is recorded on the
run step, and cost is attributed to the provider that answered, or, for
an image call that timed out, to the provider it was waiting on.

## Streams

The response starts when the model's first chunk arrives, so a refusal before
the stream (a limit, a budget, a policy) answers with its own status code.
A failure part way through ends the stream with an OpenAI error event. A
stream the client abandons fails its run with `CLIENT_DISCONNECTED`, and SOIT
closes the provider stream and ends the model step as `canceled`
(`STREAM_ABANDONED`).

Every stream that reached the provider is charged, however it ends. Providers
report usage only at the end of a stream, so a stream that ends without it
(the client left, the stream failed part way, or the backend never sends
usage) is charged an estimate from the prompt and from the text the model
generated. The estimate is flagged `usage_estimated` on the step and in the
cost row's pricing snapshot, and it counts toward credits, budgets and the
key's daily token quota like any other call. It is close for text and a lower
bound for large images and for reasoning a model does not stream. The `usage`
a response reports is always the provider's own count; only the ledger
carries the estimate. An image call that times out after the provider was
asked is charged the images it asked for, also flagged `usage_estimated`. It
counts toward credits and budgets like any image call and, carrying no
tokens, not toward the token quota; see
[the ledger](ledger.md#charges-soit-estimates).

## Errors

Refusals use OpenAI's error body, `{"error": {"message", "type", "param",
"code"}}`, so SDKs raise their usual exception classes. `code` is SOIT's error
code in lower case.

Under `/v1/messages`, refusals use Anthropic's body instead, `{"type": "error",
"error": {"type", "message"}}`, with the same statuses and these types: `400`
`invalid_request_error`, `401` `authentication_error`, `402` `billing_error`,
`403` `permission_error`, `404` `not_found_error`, `413` `request_too_large`,
`429` `rate_limit_error` (with `Retry-After`) and `5xx` `api_error`. A failure
after a stream has started arrives as an `error` event, since the status line
is already sent.

| Status | `type` | Typical cause |
| ------ | ------ | ------------- |
| 400 | `invalid_request_error` | a malformed request, `n` above 1, an image size out of range, an image parameter SOIT does not send |
| 401 | `authentication_error` | a missing, revoked or expired key |
| 402 | `insufficient_quota` | a hard-stop budget is spent (`budget_exhausted`), or credit is exhausted |
| 403 | `permission_error` | the key's scope, model list or address list does not allow the call |
| 404 | `invalid_request_error` | the model is not configured in the workspace |
| 409 | `invalid_request_error` | the model or its provider is disabled, or the provider has no credential or governed base URL |
| 422 | `invalid_request_error` | the model lacks a capability the call needs, such as tools or embeddings, its route cannot carry an image option asked for, or the provider's host does not resolve |
| 429 | `rate_limit_error` | a rate limit or quota; `Retry-After` says when to try again |
| 5xx | `api_error` | the provider failed or timed out, and no virtual model target was left to try |

## Running the gateway on its own

The gateway can run in processes of its own, scaled and exposed apart from
the console's API. Start them with `SOIT_ROLE=gateway` and the same
configuration, database, Redis and storage as the rest of the deployment:

```bash
SOIT_ROLE=gateway uvicorn app.main:app --host 0.0.0.0 --port 9300
```

A gateway process serves `/v1`, `/mcp` with its discovery metadata under
`/.well-known`, `/api/v1/tools`, and `/health` and `/metrics`; every other
path answers `404`. It runs none of the background work (outbox dispatch,
usage aggregation, reapers, schedules, ingestion, the license heartbeat), so
a process with the default role, `SOIT_ROLE=all`, must run beside it: that is
where a call's cost reaches its aggregates, budget thresholds and alerts. The
gateway entry points reach the model hub and the other domain modules only
through the composition root, which an import contract in CI holds them to.

## Compatibility testing

`server/tests/compat` drives the official Anthropic Python SDK against
`/v1/messages` in CI (messages, the stream helper, tool use and streamed tool
input, token counting, the models list and error classes), and the OpenAI
Python SDK against the rest of the gateway:
completions, streams, tool calls, structured output, base64 embeddings, model
listing, image generation and edits, and error classes. LangChain's
`ChatOpenAI` and the Agents SDK's chat-completions model call through that
same client.

## Known limitations

- A call that fails, or records no cost, keeps its budget hold until its
  run ends (for a gateway call, when the call returns), or at most its
  timeout (`LLM_TIMEOUT_SECONDS`, or `LLM_IMAGE_TIMEOUT_SECONDS` for images)
  and a minute. A call still running after that, such as a very long stream,
  no longer holds its budget. While Redis is unreachable, replicas do not see
  each other's holds and can each overshoot a budget by about one call.
- Budget spend reads the daily aggregates for finished days and the cost
  ledger for today; a day's aggregate is rebuilt by the reconciler
  (`USAGE_RECONCILE_INTERVAL_SECONDS`, hourly by default).
- Content capture is decided when a run starts; if the workspace setting
  cannot be read, content is withheld.
- A key's calls-per-minute and daily limits count the tool calls made with
  it through `/api/v1/tools` and `/mcp`, but not the tool calls an agent or a
  workflow makes inside a run; those are held by the member's own tool
  limits, the key's allowed tools and budgets.
- A direct tool call that waits for approval runs only when the caller sends
  it again; nothing runs it on the caller's behalf.
