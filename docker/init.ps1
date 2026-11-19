# Write docker/.env for the lite profile with fresh secrets.
#
#   powershell -ExecutionPolicy Bypass -File docker/init.ps1
#   powershell -ExecutionPolicy Bypass -File docker/init.ps1 -Domain soit.example.com [-Email admin@example.com]
#
# Then: docker compose -f docker/docker-compose.lite.yml up -d
#
# It never overwrites docker/.env, and refuses to run when a lite database
# already exists: a new SECRET_KEY would leave every sealed secret unreadable
# and a new database password would not open the existing database.
param(
    [string]$Domain = "",
    [string]$Email = "admin@example.com"
)

$ErrorActionPreference = "Stop"
$envFile = Join-Path $PSScriptRoot ".env"

if (Test-Path $envFile) {
    Write-Error "$envFile already exists; leaving it as it is."
    exit 1
}
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker volume inspect soit-lite_postgres_data *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Error "A lite database (volume soit-lite_postgres_data) already exists. Fresh secrets would lock it out. Write $envFile by hand with the values it was created with."
        exit 1
    }
}

function New-RandomHex([int]$bytes) {
    $buffer = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

$adminPassword = New-RandomHex 12
$lines = @(
    "# Written by docker/init.ps1 on $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')).",
    "# Back this file up with the database and never change SECRET_KEY:",
    "# stored secrets are sealed with a key derived from it.",
    "SECRET_KEY=$(New-RandomHex 32)",
    "DATABASE_PASS=$(New-RandomHex 16)",
    "BOOTSTRAP_ADMIN_EMAIL=$Email",
    "BOOTSTRAP_ADMIN_PASSWORD=$adminPassword"
)
if ($Domain) {
    $lines += @(
        "",
        "# Production: HTTPS for $Domain, with a certificate Caddy obtains.",
        "# Point the domain's DNS at this host and open ports 80 and 443.",
        "ENVIRONMENT=production",
        "SOIT_SITE_ADDRESS=$Domain",
        "HTTP_PUBLISHED_PORT=80",
        "HTTPS_PUBLISHED_PORT=443",
        "WEB_PUBLISHED_PORT=127.0.0.1:5000",
        "MCP_RESOURCE_URL=https://$Domain/mcp",
        "SYSTEM_MAIL_LINK_BASE_URL=https://$Domain"
    )
}
# LF endings and no byte order mark, which Compose reads as part of the first key.
[System.IO.File]::WriteAllText($envFile, (($lines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding $false))

Write-Output "Wrote $envFile"
Write-Output "Admin sign-in: $Email / $adminPassword"
if ($Domain) { Write-Output "Start it, then open https://${Domain}:" } else { Write-Output "Start it, then open http://localhost:5000:" }
Write-Output "  docker compose -f docker/docker-compose.lite.yml up -d"
