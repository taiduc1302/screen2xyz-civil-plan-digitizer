$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project environment not found. Run: py -3.11 -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt"
}

$env:PYTHONPATH = Join-Path $root "src"
& $python -m screen2xyz_app
exit $LASTEXITCODE

