#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Bootstrap the entire CaseGraph monorepo from a fresh clone.

.DESCRIPTION
    1. Enables corepack so the pinned pnpm version (from packageManager) is
       activated automatically — no global pnpm install required.
    2. Runs pnpm install for all JS/TS workspace packages.
    3. Creates a single Python virtual-environment (.venv) at repo root and
       installs all Python editable deps (SDK, workflows, API, agent-runtime).

.NOTES
    Prerequisites: Node.js >= 20, Python >= 3.12
    Idempotent — safe to re-run after pulling new changes.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    # ---------------------------------------------------------------
    # 1. Node / pnpm (via corepack — version pinned in packageManager)
    # ---------------------------------------------------------------
    Write-Host "`n==> Enabling corepack ..." -ForegroundColor Cyan
    corepack enable

    Write-Host "==> Installing JS/TS dependencies (pnpm) ..." -ForegroundColor Cyan
    pnpm install --frozen-lockfile

    # ---------------------------------------------------------------
    # 2. Python — single venv for all Python apps
    # ---------------------------------------------------------------
    $Venv = Join-Path $RepoRoot '.venv'
    if (-not (Test-Path (Join-Path $Venv 'Scripts/python.exe'))) {
        Write-Host "`n==> Creating Python venv at $Venv ..." -ForegroundColor Cyan
        python -m venv $Venv
    }
    $Python = Join-Path $Venv 'Scripts/python.exe'

    Write-Host "==> Upgrading pip ..." -ForegroundColor Cyan
    & $Python -m pip install --quiet --upgrade pip

    Write-Host "==> Installing Python packages (SDK + workflows + API + runtime) ..." -ForegroundColor Cyan
    & $Python -m pip install --quiet `
        -e "packages/agent-sdk" `
        -e "packages/workflows" `
        -e "apps/api[dev,observability]" `
        -e "apps/agent-runtime[dev]"

    # ---------------------------------------------------------------
    # 3. Seed .env from example if missing
    # ---------------------------------------------------------------
    $EnvFile = Join-Path $RepoRoot '.env'
    $EnvExample = Join-Path $RepoRoot '.env.example'
    if ((-not (Test-Path $EnvFile)) -and (Test-Path $EnvExample)) {
        Write-Host "==> Copying .env.example → .env (edit to add API keys)" -ForegroundColor Yellow
        Copy-Item $EnvExample $EnvFile
    }

    # ---------------------------------------------------------------
    # 4. Summary
    # ---------------------------------------------------------------
    Write-Host "`n✅  Bootstrap complete." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Activate Python :  .venv\Scripts\activate" -ForegroundColor White
    Write-Host ""
    Write-Host "  Frontend        :  pnpm dev:web                                          →  http://localhost:3000"
    Write-Host "  API             :  cd apps/api && uvicorn app.main:app --reload --port 8000"
    Write-Host "  Agent runtime   :  cd apps/agent-runtime && uvicorn app.main:app --reload --port 8100"
    Write-Host "  Validate all    :  pnpm validate"
    Write-Host ""
}
finally {
    Pop-Location
}
