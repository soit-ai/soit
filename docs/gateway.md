# OpenAI-compatible gateway

SOIT serves an OpenAI-compatible API under `/v1`, next to its own API under
`/api/v1`. Any client built for OpenAI (the official SDKs, LangChain, the
OpenAI Agents SDK, most tools that accept a base URL) can call the models a
workspace has configured, and every call is governed the way SOIT's own
agents are: rate limits, quotas, budgets, content safety, cost recording and
audit.

Examples for curl, Python, Node, LangChain and the Agents SDK are in
[`examples/gateway/`](../examples/gateway/).

## Connecting

| Setting  | Value |
| -------- | ----- |
| Base URL | the API address plus `/v1`, e.g. `http://localhost:9200/v1` |
| API key  | a SOIT API key, sent as `Authorization: Bearer sk_…` |
| Model    | a model ref, `model:{provider}:{model}`, or a virtual model, `vmodel:{slug}` |

`GET /v1/models` lists what the key may call, by the name a call uses.

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
| `POST /v1/images/generations` | `n`, `size` (64 to 4096 pixels a side, or `auto`), `response_format`. |
| `POST /v1/images/edits` | Multipart `image` and optional `mask`. As in OpenAI's API, the mask's transparent pixels mark the area to edit. |

Fields SOIT does not know are ignored rather than refused, so clients that
send newer OpenAI parameters keep working. The Responses API
(`/v1/responses`), Assistants, files, audio, batch and fine-tuning are not
served.

On models reached through OpenAI's Responses API (the GPT-5.5 family on an
`openai` provider), `stop` is refused because that API cannot honour it, and
`seed` is not sent.

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

## What a key may do

Limits set on a key apply on top of its owner's own limits; an empty limit
means none of that kind. Set them in **Settings › API** or with
`PATCH /api/v1/api-keys/{key_id}`; rotation keeps them.

| Limit | Refusal |
| ----- | ------- |
| Calls per minute | `429`, `Retry-After` |
| Calls per 24 hours | `429`, `Retry-After` |
| Tokens per UTC day | `429`, `Retry-After` |
| Allowed addresses (addresses or CIDR ranges) | `403` |
| Allowed models (`model:` and `vmodel:` refs) | `403`; `/v1/models` lists only these |
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
- Admitted calls hold a short reservation of the average call cost, so
  concurrent callers overshoot a limit by about one call at most.
- Crossing a threshold (50, 80 and 100 percent by default) notifies workspace
  owners and admins once per budget, period and threshold, in their inboxes,
  on their own endpoints as their preferences allow, and on the workspace's
  team channels subscribed to alerts.

## Content-free runs

When prompts and outputs must not be stored, set the workspace's
`content_capture` to `metadata_only` (**Settings › Security**), or ask for it
on one key. Run and step summaries, output previews and error text are then
stored as a length and a SHA-256 prefix; statuses, error codes, tokens,
costs and timings are recorded as before, and callers still get their
answers. A key can tighten its workspace's mode but not loosen it. A
workspace admin may switch a workspace to `metadata_only`; only a tenant
admin may switch it back.

## Virtual models

A virtual model is a workspace name, called as `vmodel:{slug}`, for an
ordered list of up to eight `model:` refs. Edit them under **Build › Models ›
Virtual models** or with `/api/v1/modelhub/virtual-models`.

A call tries the targets in order. A target that is unavailable (disabled,
removed, or missing a capability the call needs) is skipped. A call that
fails with a timeout, `408`, `409`, `429`, a `5xx` or a lost connection moves
to the next target once that target's own retries are spent. An invalid
request or a policy refusal is not repeated elsewhere; a stream moves on only
before its first chunk; an image call is never repeated on another provider,
because the failed one may have billed it. Each attempt is recorded on the
run step, and cost is attributed to the provider that answered.

## Streams

The response starts when the model's first chunk arrives, so a refusal before
the stream (a limit, a budget, a policy) answers with its own status code.
A failure part way through ends the stream with an OpenAI error event. A
stream the client abandons fails its run with `CLIENT_DISCONNECTED`.

## Errors

Refusals use OpenAI's error body, `{"error": {"message", "type", "param",
"code"}}`, so SDKs raise their usual exception classes. `code` is SOIT's error
code in lower case.

| Status | `type` | Typical cause |
| ------ | ------ | ------------- |
| 400 | `invalid_request_error` | a malformed request, `n` above 1, an image size out of range |
| 401 | `authentication_error` | a missing, revoked or expired key |
| 402 | `insufficient_quota` | a hard-stop budget is spent (`budget_exhausted`), or credit is exhausted |
| 403 | `permission_error` | the key's scope, model list or address list does not allow the call |
| 404 | `invalid_request_error` | the model is not configured in the workspace |
| 409 | `invalid_request_error` | the model or its provider is disabled |
| 422 | `invalid_request_error` | the model lacks a capability the call needs, such as tools or embeddings |
| 429 | `rate_limit_error` | a rate limit or quota; `Retry-After` says when to try again |
| 5xx | `api_error` | the provider failed or timed out, and no virtual model target was left to try |

## Compatibility testing

`server/tests/compat` drives the OpenAI Python SDK against the gateway in CI:
completions, streams, tool calls, structured output, base64 embeddings, model
listing, image generation and edits, and error classes. LangChain's
`ChatOpenAI` and the Agents SDK's chat-completions model call through that
same client.

## Known limitations

- A stream the client abandons ends its run, but the model step stays
  `running` and its cost is not recorded.
- Budget reservations expire after about a minute rather than being released,
  and without Redis they are skipped, so concurrent calls can overshoot a
  budget by more than one call.
- Budget spend reads the daily aggregates for finished days and the cost
  ledger for today; a day's aggregate is rebuilt by the reconciler
  (`USAGE_RECONCILE_INTERVAL_SECONDS`, hourly by default).
- Content capture is decided when a run starts; if the workspace setting
  cannot be read, content is withheld.
