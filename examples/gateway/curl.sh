#!/usr/bin/env bash
# Call SOIT's OpenAI-compatible gateway with curl.
#
#   SOIT_BASE_URL  e.g. http://localhost:9200/v1
#   SOIT_API_KEY   a SOIT API key from Settings > API
#   SOIT_MODEL     a model ref from GET /v1/models, or vmodel:{slug}
set -euo pipefail

: "${SOIT_BASE_URL:=http://localhost:9200/v1}"
: "${SOIT_API_KEY:?Set SOIT_API_KEY to a SOIT API key}"
: "${SOIT_MODEL:?Set SOIT_MODEL to a model ref from GET /v1/models}"

auth=(-H "Authorization: Bearer ${SOIT_API_KEY}" -H "Content-Type: application/json")

echo "== models the key may call"
curl -sS "${SOIT_BASE_URL}/models" "${auth[@]}" | jq -r '.data[].id'

echo "== chat completion (the run id is in the x-soit-run-id header)"
curl -sS -D - "${SOIT_BASE_URL}/chat/completions" "${auth[@]}" \
  -d "$(jq -n --arg model "$SOIT_MODEL" '{
        model: $model,
        messages: [{role: "user", content: "Say hello in five words."}]
      }')" \
  | grep -i -e '^x-soit-run-id' -e '"content"'

echo "== streamed completion"
curl -sS -N "${SOIT_BASE_URL}/chat/completions" "${auth[@]}" \
  -d "$(jq -n --arg model "$SOIT_MODEL" '{
        model: $model,
        stream: true,
        stream_options: {include_usage: true},
        messages: [{role: "user", content: "Count to five."}]
      }')"
echo
