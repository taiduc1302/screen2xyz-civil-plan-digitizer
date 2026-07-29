#requires -version 5.1
<#
Screen2XYZ M2-Live - demo/self-test launcher.

Runs the automated self-test against the safe synthetic demo target (no real
application needed) and prints a PASS/FAIL report. Pass -Interactive to just
open the demo target window instead.

Launch with right-click -> "Run with PowerShell" (double-clicking a .ps1 only
opens it in an editor). The window is ALWAYS held open at the end so you can
read the report - the whole point of the demo is that report, so it must not
flash and vanish on the PASS path.
#>

param([switch]$Interactive)

$ErrorActionPreference = "Stop"
try {
    $RepoRoot = $PSScriptRoot
    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "ERROR: Python virtual environment not found at:" -ForegroundColor Red
        Write-Host "  $VenvPython" -ForegroundColor Red
        Write-Host "Create it once: python -m venv .venv" -ForegroundColor Yellow
        Read-Host "Press Enter to close"
        exit 1
    }
    $env:PYTHONPATH = Join-Path $RepoRoot "src"
    if ($Interactive) {
        & $VenvPython -m screen2xyz_m2 demo --interactive
    } else {
        & $VenvPython -m screen2xyz_m2 demo
    }
    $exitCode = $LASTEXITCODE
    Write-Host ""
    if ($exitCode -eq 0) {
        Write-Host "Demo self-test: PASS" -ForegroundColor Green
    } else {
        Write-Host "Demo self-test: FAIL (exit code $exitCode)." -ForegroundColor Red
        Write-Host "A 'demo target did not acknowledge ... within Ns' timeout is a" -ForegroundColor Yellow
        Write-Host "known, bounded, rare OS message-pump contention case - just run" -ForegroundColor Yellow
        Write-Host "this again. Any other failure is a real one." -ForegroundColor Yellow
    }
    Read-Host "Press Enter to close"
    exit $exitCode
} catch {
    Write-Host ""
    Write-Host "Launcher error: $_" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
