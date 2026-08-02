[CmdletBinding()]
param(
    [string]$Executable = "dist\Screen2XYZ-Setup\Screen2XYZ.exe"
)

$ErrorActionPreference = "Stop"
$resolved = Resolve-Path -LiteralPath $Executable
$bundleRoot = Split-Path -Parent $resolved
foreach ($helper in @("ocr_windows_boxes.ps1", "ocr_tesseract_rotated.ps1")) {
    $helperPath = Join-Path $bundleRoot "_internal\screen2xyz_civil\adapters\$helper"
    if (-not (Test-Path -LiteralPath $helperPath)) {
        throw "Packaged OCR fallback helper is missing: $helperPath"
    }
}
$env:SCREEN2XYZ_SKIP_FIRST_RUN = "1"
$process = Start-Process -FilePath $resolved -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 4
    $running = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
    if ($null -eq $running) {
        throw "Packaged executable exited during launch smoke"
    }
    $running.Refresh()
    if ($running.MainWindowTitle -notmatch "Screen2XYZ") {
        throw "Packaged Screen2XYZ window was not detected"
    }
    Write-Host "Packaged executable launch smoke PASS: $($running.MainWindowTitle)"
} finally {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
}
