#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Canonical whole-repo validation.  One command, one pass/fail verdict.

.DESCRIPTION
    Runs every gate that must pass before code is considered valid:

    1. Python API tests            (pytest, ~600 tests)
    2. TypeScript typecheck         (tsc --noEmit on apps/web)
    3. Next.js production build     (next build)
    4. API import smoke             (import app.main, count routes >= 140)
    5. Agent-runtime import smoke   (import app.main, count routes)
    6. SDK barrel integrity         (Python __all__ resolves, count >= 575)
    7. Contract duplication guard   (no SDK/workflow types re-defined in layers)
    8. Eval config integrity        (Promptfoo YAMLs parse, datasets exist, registry consistent)
    9. STATUS.md freshness          (regenerate and diff — must match HEAD)

    Exit code 0 = all gates pass.  Non-zero = at least one failed.

.EXAMPLE
    pwsh scripts/validate.ps1
    pnpm validate
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

$script:failures = @()
$script:passCount = 0
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

function Run-Gate {
    param(
        [string]$Name,
        [scriptblock]$Block
    )
    Write-Host "`n────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host "  [$($script:passCount + $script:failures.Count + 1)] $Name" -ForegroundColor Cyan
    Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & $Block
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "Process exited with code $LASTEXITCODE"
        }
        $sw.Stop()
        Write-Host "  PASS  ($([math]::Round($sw.Elapsed.TotalSeconds, 1))s)" -ForegroundColor Green
        $script:passCount++
    }
    catch {
        $sw.Stop()
        Write-Host "  FAIL  $($_.Exception.Message)" -ForegroundColor Red
        $script:failures += $Name
    }
}

# Resolve python — canonical location is .venv at repo root
$Python = Join-Path $RepoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: .venv not found at $RepoRoot — run 'pnpm bootstrap' first." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

Run-Gate 'Python API tests' {
    Push-Location (Join-Path $RepoRoot 'apps/api')
    try {
        & $Python -m pytest tests -q --tb=short 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "pytest failed (exit $LASTEXITCODE)" }
    }
    finally { Pop-Location }
}

Run-Gate 'TypeScript typecheck' {
    Push-Location $RepoRoot
    try {
        pnpm typecheck 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "tsc failed (exit $LASTEXITCODE)" }
    }
    finally { Pop-Location }
}

Run-Gate 'Next.js production build' {
    Push-Location $RepoRoot
    try {
        pnpm build:web 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "next build failed (exit $LASTEXITCODE)" }
    }
    finally { Pop-Location }
}

Run-Gate 'API import smoke' {
    Push-Location (Join-Path $RepoRoot 'apps/api')
    try {
        $out = & $Python -c "from app.thresholds import MIN_API_ROUTES; from app.main import app; routes=len(app.routes); assert routes >= MIN_API_ROUTES, f'Only {routes} routes (need {MIN_API_ROUTES})'; print(f'app.main loaded \u2014 {routes} routes')" 2>&1
        $out | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "API import smoke failed" }
    }
    finally { Pop-Location }
}

Run-Gate 'Agent-runtime import smoke' {
    Push-Location (Join-Path $RepoRoot 'apps/agent-runtime')
    try {
        $out = & $Python -c "import sys; sys.path.insert(0,'..\\apps\\api'); from app.thresholds import MIN_AGENT_RUNTIME_ROUTES as T; from app.main import app; routes=len(app.routes); assert routes >= T, f'Only {routes} routes (need {T})'; print(f'app.main loaded — {routes} routes')" 2>&1
        $out | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "Agent-runtime import smoke failed" }
    }
    finally { Pop-Location }
}

Run-Gate 'SDK barrel integrity' {
    $out = & $Python -c "import sys; sys.path.insert(0,'apps/api'); from app.thresholds import MIN_SDK_PYTHON_EXPORTS as T; from casegraph_agent_sdk import __all__ as a; n=len(a); assert n >= T, f'Only {n} exports (need {T})'; print(f'SDK barrel OK \u2014 {n} Python exports')" 2>&1
    $out | ForEach-Object { Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) { throw "SDK barrel check failed" }
}

Run-Gate 'Contract duplication guard' {
    $out = & $Python (Join-Path $RepoRoot 'scripts/check_contract_duplication.py') 2>&1
    $out | ForEach-Object { Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) { throw "Contract duplication check failed" }
}

Run-Gate 'Eval config integrity' {
    Push-Location (Join-Path $RepoRoot 'apps/api')
    try {
        & $Python -m pytest tests/test_eval_readiness.py -q --tb=short 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "Eval readiness tests failed (exit $LASTEXITCODE)" }
    }
    finally { Pop-Location }
}

Run-Gate 'STATUS.md freshness' {
    Push-Location (Join-Path $RepoRoot 'apps/api')
    try {
        $tmpFile = [System.IO.Path]::GetTempFileName()
        & $Python (Join-Path $RepoRoot 'scripts/generate_status.py') --write-to $tmpFile 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "generate_status.py failed" }
        $statusFile = Join-Path $RepoRoot 'STATUS.md'
        if (-not (Test-Path $statusFile)) { throw "STATUS.md does not exist — run: pnpm generate:status" }
        $expected = (Get-Content $tmpFile -Raw -Encoding utf8) -replace 'on \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC', 'on DATE'
        $actual = (Get-Content $statusFile -Raw -Encoding utf8) -replace 'on \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC', 'on DATE'
        Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
        if ($expected.Trim() -ne $actual.Trim()) {
            throw "STATUS.md is stale. Run: pnpm generate:status"
        }
        Write-Host "    STATUS.md is fresh"
    }
    finally { Pop-Location }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

$stopwatch.Stop()
$total = $script:passCount + $script:failures.Count
Write-Host "`n════════════════════════════════════════" -ForegroundColor DarkGray
if ($script:failures.Count -eq 0) {
    Write-Host "  ALL $total GATES PASSED  ($([math]::Round($stopwatch.Elapsed.TotalSeconds, 1))s)" -ForegroundColor Green
}
else {
    Write-Host "  $($script:failures.Count)/$total GATES FAILED  ($([math]::Round($stopwatch.Elapsed.TotalSeconds, 1))s)" -ForegroundColor Red
    foreach ($f in $script:failures) {
        Write-Host "    ✗ $f" -ForegroundColor Red
    }
}
Write-Host "════════════════════════════════════════`n" -ForegroundColor DarkGray

exit $script:failures.Count
