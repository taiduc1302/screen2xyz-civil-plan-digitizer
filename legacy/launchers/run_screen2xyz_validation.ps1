#requires -version 5.1
<#
Screen2XYZ M2-Live - real-target validation (G-E-REAL) launcher.

Launches the guided Tk validation wizard against a REAL application window
you select. It will ask you to confirm the target contains only authorized,
non-confidential content before doing anything else, then walks the real
setup/region-selection/preview/recording screens, and writes a sanitized
JSON report (no screenshots, no window title) under the ignored run root.

Launch with right-click -> "Run with PowerShell" (double-clicking a .ps1 only
opens it in an editor). The window is always held open with the result.
#>

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
    & $VenvPython -m screen2xyz_m2 validate-real-target
    $exitCode = $LASTEXITCODE
    Write-Host ""
    switch ($exitCode) {
        0 { Write-Host "Result: PASS" -ForegroundColor Green }
        2 { Write-Host "Result: BLOCKED (see the report for the reason)" -ForegroundColor Yellow }
        default { Write-Host "Result: FAIL (exit code $exitCode)" -ForegroundColor Red }
    }
    Read-Host "Press Enter to close"
    exit $exitCode
} catch {
    Write-Host ""
    Write-Host "Launcher error: $_" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
