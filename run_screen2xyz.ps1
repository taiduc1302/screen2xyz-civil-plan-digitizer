#requires -version 5.1
<#
Screen2XYZ M2-Live - normal application launcher.

IMPORTANT: Windows opens a double-clicked .ps1 in an editor, it does NOT run
it. Launch this with right-click -> "Run with PowerShell", or from a terminal
with:  powershell -ExecutionPolicy Bypass -File .\run_screen2xyz.ps1
(that -ExecutionPolicy Bypass only affects this one launch, never the system).

The repo root is resolved from THIS script's own location ($PSScriptRoot),
not the caller's current directory, and the window is kept open on any error.
The app runs purely from PYTHONPATH=src with only the Python standard library
(tkinter/ctypes) - there are no third-party dependencies to install, so a
bare `python -m venv .venv` is all the setup that is needed.
#>

$ErrorActionPreference = "Stop"
try {
    $RepoRoot = $PSScriptRoot
    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "ERROR: Python virtual environment not found at:" -ForegroundColor Red
        Write-Host "  $VenvPython" -ForegroundColor Red
        Write-Host ""
        Write-Host "Create it once from the repository root (no dependencies to install):" -ForegroundColor Yellow
        Write-Host "  python -m venv .venv" -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Press Enter to close"
        exit 1
    }
    $env:PYTHONPATH = Join-Path $RepoRoot "src"
    & $VenvPython -m screen2xyz_m2 ui
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Write-Host ""
        Write-Host "screen2xyz_m2 exited with code $exitCode. See the output above." -ForegroundColor Red
        Read-Host "Press Enter to close"
    }
    exit $exitCode
} catch {
    Write-Host ""
    Write-Host "Launcher error: $_" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
