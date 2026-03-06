$ErrorActionPreference = "Stop"

# Resolve repo root from docker/ directory.
$rootDir = Split-Path -Parent $PSScriptRoot
Set-Location $rootDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "docker is required but not found in PATH."
  exit 1
}

docker compose up -d
docker compose run --rm api uv run alembic upgrade head

$adminEmail = $env:ADMIN_EMAIL
if (-not $adminEmail) { $adminEmail = "admin@example.com" }
$adminPassword = $env:ADMIN_PASSWORD
if (-not $adminPassword) { $adminPassword = "changeme123" }

docker compose run --rm api uv run python scripts/bootstrap_admin.py --email $adminEmail --password $adminPassword
