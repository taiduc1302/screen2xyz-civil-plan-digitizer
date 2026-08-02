$ErrorActionPreference = "Stop"

try {
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Project environment not found. Run: py -3.11 -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt"
    }
    $env:PYTHONPATH = Join-Path $PSScriptRoot "src"
    & $python -m screen2xyz_app
    if ($LASTEXITCODE -ne 0) {
        throw "Screen2XYZ exited with code $LASTEXITCODE"
    }
} catch {
    Write-Host "Screen2XYZ could not start: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
