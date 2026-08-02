#requires -version 5.1
<#
Screen2XYZ Civil Plan Digitizer - local preliminary civil review launcher.

Launch with right-click -> "Run with PowerShell", or:
  powershell -ExecutionPolicy Bypass -File .\run_civil_plan_digitizer.ps1
#>

$ErrorActionPreference = "Stop"
try {
    $RepoRoot = $PSScriptRoot
    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "ERROR: Python virtual environment not found at:" -ForegroundColor Red
        Write-Host "  $VenvPython" -ForegroundColor Red
        Write-Host ""
        Write-Host "Create it once: py -3.14 -m venv --without-pip .venv" -ForegroundColor Yellow
        Read-Host "Press Enter to close"
        exit 1
    }
    $env:PYTHONPATH = Join-Path $RepoRoot "src"
    & $VenvPython -m screen2xyz_civil ui
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Write-Host ""
        Write-Host "Civil Plan Digitizer exited with code $exitCode." -ForegroundColor Red
        Read-Host "Press Enter to close"
    }
    exit $exitCode
} catch {
    Write-Host ""
    Write-Host "Civil Plan Digitizer launcher error: $_" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
