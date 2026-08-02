#requires -version 5.1
<#
Screen2XYZ M2-Live - simple text launch menu.

Delegates to the dedicated launchers so the result-display and window-hold
behavior are shared (not re-implemented and out of sync). Launch with
right-click -> "Run with PowerShell".
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

    Write-Host "Screen2XYZ M2-Live" -ForegroundColor Cyan
    Write-Host "1) Normal application"
    Write-Host "2) Demo (automated self-test)"
    Write-Host "3) Demo (interactive - just open the target window)"
    Write-Host "4) Real-target validation (G-E-REAL)"
    Write-Host "5) Civil Plan Digitizer"
    Write-Host "6) Open latest run folder"
    Write-Host "7) Help (open the public guide)"
    Write-Host "Q) Quit"
    $choice = Read-Host "Choose an option"

    switch ($choice) {
        "1" { & (Join-Path $RepoRoot "run_screen2xyz.ps1") }
        "2" { & (Join-Path $RepoRoot "run_screen2xyz_demo.ps1") }
        "3" { & (Join-Path $RepoRoot "run_screen2xyz_demo.ps1") -Interactive }
        "4" { & (Join-Path $RepoRoot "run_screen2xyz_validation.ps1") }
        "5" { & (Join-Path $RepoRoot "run_civil_plan_digitizer.ps1") }
        "6" {
            $runsRoot = Join-Path $RepoRoot ".lab_work\m2_runs"
            if (Test-Path $runsRoot) {
                $latest = Get-ChildItem $runsRoot -Directory |
                    Sort-Object LastWriteTime -Descending | Select-Object -First 1
                if ($latest) { Invoke-Item $latest.FullName }
                else { Write-Host "No runs found yet under $runsRoot" -ForegroundColor Yellow }
            } else {
                Write-Host "No runs folder yet - nothing has been recorded." -ForegroundColor Yellow
            }
            Read-Host "Press Enter to close"
        }
        "7" {
            $guide = Join-Path $RepoRoot "docs\public\Screen2XYZ_M2_Guide_v0.1.md"
            if (Test-Path $guide) { Invoke-Item $guide }
            else { Write-Host "Guide not found at $guide" -ForegroundColor Yellow }
            Read-Host "Press Enter to close"
        }
        default { Write-Host "Exiting." }
    }
} catch {
    Write-Host ""
    Write-Host "Menu error: $_" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
