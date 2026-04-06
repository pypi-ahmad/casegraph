# Run a Promptfoo eval suite from the services/evals directory.
# Usage: .\scripts\run-promptfoo.ps1 <config-name>
# Example: .\scripts\run-promptfoo.ps1 provider-comparison
param(
    [Parameter(Position=0)]
    [string]$ConfigName
)

$ErrorActionPreference = "Stop"
$EvalsDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not $ConfigName) {
    Write-Host "Usage: .\scripts\run-promptfoo.ps1 <config-name>"
    Write-Host "Available configs:"
    Get-ChildItem "$EvalsDir\promptfoo\*.yaml" | ForEach-Object { $_.BaseName }
    exit 1
}

$ConfigFile = Join-Path $EvalsDir "promptfoo\$ConfigName.yaml"
if (-not (Test-Path $ConfigFile)) {
    Write-Error "Config file not found: $ConfigFile"
    exit 1
}

# Load env if available
$EnvFile = Join-Path $EvalsDir "config\.env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
        }
    }
}

if (-not $env:CASEGRAPH_API_URL) {
    $env:CASEGRAPH_API_URL = "http://localhost:8000"
}

New-Item -ItemType Directory -Force -Path (Join-Path $EvalsDir "results") | Out-Null

Write-Host "Running Promptfoo eval: $ConfigName"
Set-Location $EvalsDir
npx promptfoo@latest eval -c $ConfigFile
Write-Host "Done. View results: npx promptfoo@latest view"
