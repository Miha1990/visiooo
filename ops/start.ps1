param([switch]$SQLite)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (!(Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create virtual environment' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if (!(Test-Path -LiteralPath 'app/.env')) {
    Copy-Item -LiteralPath 'app/.env.example' -Destination 'app/.env'
    & ./.venv/Scripts/python.exe -c "from pathlib import Path; import secrets; p=Path('app/.env'); p.write_text(p.read_text(encoding='utf-8').replace('SECRET_KEY=', 'SECRET_KEY='+secrets.token_urlsafe(64)), encoding='utf-8')"
}
$env:DEBUG = 'true'
$env:ENVIRONMENT = 'local'
if ($SQLite) {
    $env:DATABASE_URL = ''
} else {
    docker compose up -d --wait db
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop or use -SQLite for local development.' }
    $dbPassword = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { 'local-vizitka-only' }
    $dbEncodedPassword = [Uri]::EscapeDataString($dbPassword)
    $env:DATABASE_URL = "postgresql://vizitka:${dbEncodedPassword}@127.0.0.1:5437/vizitka"
}
& ./.venv/Scripts/python.exe app/manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migrations failed' }
& ./.venv/Scripts/python.exe app/manage.py runserver 127.0.0.1:8000
