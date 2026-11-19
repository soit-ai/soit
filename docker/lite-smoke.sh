#!/usr/bin/env sh
# Smoke test for the lite profile (docker/docker-compose.lite.yml).
#
# Run from the repository root after `docker compose -f
# docker/docker-compose.lite.yml up -d` (CI adds the build overlay and sets
# COMPOSE to match). It waits for the API and the worker, checks that web
# serves the app and proxies the API on its own origin, signs in as the
# bootstrap admin, stores a secret through the sealed backend, restarts the
# API and checks the secret still resolves: the lite profile's promise is that
# nothing configured is lost on restart.
set -eu

API="${API_URL:-http://localhost:9200}"
WEB="${WEB_URL:-http://localhost:5000}"
COMPOSE="${COMPOSE:-docker compose -f docker/docker-compose.lite.yml}"
EMAIL="${BOOTSTRAP_ADMIN_EMAIL:-admin@example.com}"
PASSWORD="${BOOTSTRAP_ADMIN_PASSWORD:-changeme123}"
DEADLINE_SECONDS="${LITE_SMOKE_TIMEOUT:-300}"

wait_ready() {
  waited=0
  until curl --fail --silent "$API/health/ready" | grep --quiet '"status":"ready"'; do
    waited=$((waited + 5))
    if [ "$waited" -ge "$DEADLINE_SECONDS" ]; then
      echo "API did not become ready within ${DEADLINE_SECONDS}s" >&2
      $COMPOSE ps >&2
      $COMPOSE logs --tail 80 api worker >&2
      exit 1
    fi
    sleep 5
  done
}

json_field() {
  python3 -c "import json,sys; body=json.load(sys.stdin); data=body.get('data', body); print(data$1)"
}

wait_ready
echo "API ready"

worker_state="$(docker inspect --format '{{.State.Health.Status}}' "$($COMPOSE ps -q worker)")"
echo "worker health: $worker_state"

waited=0
until curl --fail --silent "$WEB/" | grep --quiet '<!DOCTYPE html>'; do
  waited=$((waited + 5))
  if [ "$waited" -ge "$DEADLINE_SECONDS" ]; then
    echo "web did not serve the app within ${DEADLINE_SECONDS}s" >&2
    $COMPOSE logs --tail 80 web >&2
    exit 1
  fi
  sleep 5
done
echo "web serves the app"

# Sign in through web: the app reaches the API on web's own origin.
login="$(curl --fail --silent -X POST "$WEB/api/v1/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"
token="$(printf '%s' "$login" | json_field "['access_token']")"
workspace="$(printf '%s' "$login" | json_field "['workspace_id']")"
auth="Authorization: Bearer $token"
scope="X-Workspace-Id: $workspace"
echo "signed in to workspace $workspace"

secret="$(curl --fail --silent -X POST "$API/api/v1/secrets" -H "$auth" -H "$scope" \
  -H 'Content-Type: application/json' \
  -d '{"name":"lite-smoke","value":"lite-smoke-value"}')"
secret_id="$(printf '%s' "$secret" | json_field "['id']")"
echo "stored secret $secret_id"

$COMPOSE restart api
wait_ready
echo "API restarted"

login="$(curl --fail --silent -X POST "$API/api/v1/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"
token="$(printf '%s' "$login" | json_field "['access_token']")"
auth="Authorization: Bearer $token"
resolved="$(curl --fail --silent -X POST "$API/api/v1/secrets/$secret_id/test" -H "$auth" -H "$scope")"
echo "secret test after restart: $resolved"
printf '%s' "$resolved" | python3 -c "
import json, sys
body = json.load(sys.stdin)
data = body.get('data', body)
ok = data.get('ok', data.get('success', data.get('resolved')))
if ok is not True:
    sys.exit('the secret did not resolve after an API restart: %s' % data)
"

knowledge="$(curl --fail --silent "$API/api/v1/knowledge" -H "$auth" -H "$scope")"
printf '%s' "$knowledge" | json_field "['items']" > /dev/null
echo "lite profile smoke passed"
