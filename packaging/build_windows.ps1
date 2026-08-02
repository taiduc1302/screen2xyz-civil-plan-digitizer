[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$DistPath = "dist",
    [string]$WorkPath = "build\pyinstaller"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
    & $Python -m PyInstaller --clean --noconfirm `
        --distpath $DistPath --workpath $WorkPath packaging\screen2xyz.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller exited with code $LASTEXITCODE"
    }
    $executable = Join-Path $DistPath "Screen2XYZ-Setup\Screen2XYZ.exe"
    if (-not (Test-Path -LiteralPath $executable)) {
        throw "Expected bundle executable was not created: $executable"
    }
    $size = (Get-ChildItem -LiteralPath (Split-Path $executable) -Recurse -File |
        Measure-Object -Property Length -Sum).Sum
    Write-Host ("Bundle ready: {0} ({1:N1} MiB)" -f $executable, ($size / 1MB))
} finally {
    Pop-Location
}
