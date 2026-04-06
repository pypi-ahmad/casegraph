#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Local smoke test: hit live API endpoints to verify the server is running.

.DESCRIPTION
    Requires:  uvicorn running on http://localhost:8000
    Run:       pwsh scripts/smoke-api.ps1

    Tests provider listing, document capabilities, case CRUD, and health endpoints.
    Does NOT require LLM keys — only exercises local API logic.
#>

param(
    [string]$BaseUrl = "http://localhost:8000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pass = 0
$fail = 0

function Test-Endpoint {
    param([string]$Method, [string]$Path, [int]$ExpectedStatus = 200, [string]$Body)
    $url = "$BaseUrl$Path"
    Write-Host -NoNewline "  $Method $Path ... "
    try {
        $params = @{ Uri = $url; Method = $Method; ContentType = 'application/json' }
        if ($Body) { $params['Body'] = $Body }
        $resp = Invoke-WebRequest @params -ErrorAction Stop
        if ($resp.StatusCode -eq $ExpectedStatus) {
            Write-Host "OK ($($resp.StatusCode))" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "UNEXPECTED $($resp.StatusCode)" -ForegroundColor Yellow
            $script:fail++
        }
    }
    catch {
        $status = $_.Exception.Response.StatusCode.value__
        if ($status -eq $ExpectedStatus) {
            Write-Host "OK ($status)" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
            $script:fail++
        }
    }
}

Write-Host "`n╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  CaseGraph API Local Smoke Test          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝`n" -ForegroundColor Cyan

# ── Health & info ────────────────────────────────────────────────
Write-Host "Health & info" -ForegroundColor White
Test-Endpoint GET "/health"
Test-Endpoint GET "/info"
Test-Endpoint GET "/status/modules"

# ── Providers ────────────────────────────────────────────────────
Write-Host "`nProviders" -ForegroundColor White
Test-Endpoint GET "/providers"

# ── Document capabilities ────────────────────────────────────────
Write-Host "`nDocument ingestion" -ForegroundColor White
Test-Endpoint GET "/documents/capabilities"
Test-Endpoint GET "/documents"

# ── Cases ────────────────────────────────────────────────────────
Write-Host "`nCases" -ForegroundColor White
Test-Endpoint GET "/cases"

$caseBody = '{"title":"Smoke test case","category":"test","domain_pack_id":"medical_insurance_us","case_type_id":"medical_insurance_us:prior_auth_review"}'
Test-Endpoint POST "/cases" -ExpectedStatus 200 -Body $caseBody

# ── Domain packs ─────────────────────────────────────────────────
Write-Host "`nDomain packs" -ForegroundColor White
Test-Endpoint GET "/domains/packs"
Test-Endpoint GET "/domains/case-types"

# ── Workflow packs ───────────────────────────────────────────────
Write-Host "`nWorkflow packs" -ForegroundColor White
Test-Endpoint GET "/workflow-packs"

# ── Submissions ──────────────────────────────────────────────────
Write-Host "`nSubmissions" -ForegroundColor White
Test-Endpoint GET "/submission/targets"

# ── Knowledge ────────────────────────────────────────────────────
Write-Host "`nKnowledge" -ForegroundColor White
Test-Endpoint GET "/knowledge/capabilities"

# ── Summary ──────────────────────────────────────────────────────
Write-Host "`n════════════════════════════════════════" -ForegroundColor DarkGray
if ($fail -eq 0) {
    Write-Host "  ALL $($pass + $fail) SMOKE CHECKS PASSED" -ForegroundColor Green
} else {
    Write-Host "  $fail/$($pass + $fail) SMOKE CHECKS FAILED" -ForegroundColor Red
}
Write-Host "════════════════════════════════════════`n" -ForegroundColor DarkGray

exit $fail
