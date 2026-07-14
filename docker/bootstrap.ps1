$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $PSScriptRoot
Set-Location $rootDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "docker is required but not found in PATH."
  exit 1
}

docker compose -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker
