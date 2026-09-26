#!/usr/bin/env bash
# Call a workspace's tools directly through SOIT's tools API.
#
#   SOIT_API_URL   the API address, e.g. http://localhost:9200
#   SOIT_API_KEY   a SOIT API key from Settings > API, with the write scope
#   SOIT_TOOL      a tool ref from GET /api/v1/tools (default tool:function:time_now)
set -euo pipefail

: "${SOIT_API_URL:=http://localhost:9200}"
: "${SOIT_API_KEY:?Set SOIT_API_KEY to a SOIT API key}"
: "${SOIT_TOOL:=tool:function:time_now}"

auth=(-H "Authorization: Bearer ${SOIT_API_KEY}" -H "Content-Type: application/json")
key="example-$(date +%s)"

echo "== tools the key may invoke"
curl -sS "${SOIT_API_URL}/api/v1/tools" "${auth[@]}" \
  | jq -r '.data[] | "\(.ref)\t\(if .approval_required then "needs approval" else "" end)"'

echo "== invoke ${SOIT_TOOL} with Idempotency-Key ${key}"
curl -sS "${SOIT_API_URL}/api/v1/tools/${SOIT_TOOL}/invoke" "${auth[@]}" \
  -H "Idempotency-Key: ${key}" -d '{"arguments": {}}' | jq '.data'

echo "== the same key again returns the recorded outcome (replayed: true)"
curl -sS "${SOIT_API_URL}/api/v1/tools/${SOIT_TOOL}/invoke" "${auth[@]}" \
  -H "Idempotency-Key: ${key}" -d '{"arguments": {}}' | jq '.data | {run_id, status, replayed}'
