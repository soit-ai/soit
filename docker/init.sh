#!/usr/bin/env sh
# Write docker/.env for the lite profile with fresh secrets.
#
#   sh docker/init.sh                          # a local install on :5000
#   sh docker/init.sh --domain soit.example.com [--email admin@example.com]
#                                              # production, HTTPS on 443
#
# Then: docker compose -f docker/docker-compose.lite.yml up -d
#
# It never overwrites docker/.env, and refuses to run when a lite database
# already exists: a new SECRET_KEY would leave every sealed secret unreadable
# and a new database password would not open the existing database.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
DOMAIN=""
EMAIL="admin@example.com"

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="${2:?--domain needs a hostname}"; shift 2 ;;
    --email) EMAIL="${2:?--email needs an address}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ -e "$ENV_FILE" ]; then
  echo "$ENV_FILE already exists; leaving it as it is." >&2
  exit 1
fi
if command -v docker >/dev/null 2>&1 && docker volume inspect soit-lite_postgres_data >/dev/null 2>&1; then
  echo "A lite database (volume soit-lite_postgres_data) already exists." >&2
  echo "Fresh secrets would lock it out. Write $ENV_FILE by hand with the values it was created with." >&2
  exit 1
fi

random_hex() {
  od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'
}

SECRET_KEY="$(random_hex 32)"
DATABASE_PASS="$(random_hex 16)"
ADMIN_PASSWORD="$(random_hex 12)"

umask 077
{
  echo "# Written by docker/init.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)."
  echo "# Back this file up with the database and never change SECRET_KEY:"
  echo "# stored secrets are sealed with a key derived from it."
  echo "SECRET_KEY=$SECRET_KEY"
  echo "DATABASE_PASS=$DATABASE_PASS"
  echo "BOOTSTRAP_ADMIN_EMAIL=$EMAIL"
  echo "BOOTSTRAP_ADMIN_PASSWORD=$ADMIN_PASSWORD"
  if [ -n "$DOMAIN" ]; then
    echo ""
    echo "# Production: HTTPS for $DOMAIN, with a certificate Caddy obtains."
    echo "# Point the domain's DNS at this host and open ports 80 and 443."
    echo "ENVIRONMENT=production"
    echo "SOIT_SITE_ADDRESS=$DOMAIN"
    echo "HTTP_PUBLISHED_PORT=80"
    echo "HTTPS_PUBLISHED_PORT=443"
    echo "WEB_PUBLISHED_PORT=127.0.0.1:5000"
    echo "MCP_RESOURCE_URL=https://$DOMAIN/mcp"
    echo "SYSTEM_MAIL_LINK_BASE_URL=https://$DOMAIN"
  fi
} > "$ENV_FILE"

echo "Wrote $ENV_FILE"
echo "Admin sign-in: $EMAIL / $ADMIN_PASSWORD"
if [ -n "$DOMAIN" ]; then
  echo "Start it, then open https://$DOMAIN:"
else
  echo "Start it, then open http://localhost:5000:"
fi
echo "  docker compose -f docker/docker-compose.lite.yml up -d"
