param(
    [Parameter(Mandatory = $true)][string]$ImagePath,
    [string]$Language = 'en-US',
    [int]$DelayMilliseconds = 0
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

function Await-WinRtOperation {
    param(
        [Parameter(Mandatory = $true)]$Operation,
        [Parameter(Mandatory = $true)][Type]$ResultType
    )
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1
    if ($null -eq $method) { throw 'WinRT task bridge unavailable' }
    $closed = $method.MakeGenericMethod($ResultType)
    $task = $closed.Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

try {
    if ($DelayMilliseconds -lt 0 -or $DelayMilliseconds -gt 60000) { exit 20 }
    if ($DelayMilliseconds -gt 0) { Start-Sleep -Milliseconds $DelayMilliseconds }
    $resolved = [System.IO.Path]::GetFullPath($ImagePath)
    if (-not [System.IO.File]::Exists($resolved) -or -not $resolved.EndsWith('.png', [System.StringComparison]::OrdinalIgnoreCase)) { exit 20 }

    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime]

    $file = Await-WinRtOperation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($resolved)) ([Windows.Storage.StorageFile])
    $stream = Await-WinRtOperation ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await-WinRtOperation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-WinRtOperation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $languageObject = New-Object Windows.Globalization.Language($Language)
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($languageObject)
    if ($null -eq $engine) { exit 22 }

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $result = Await-WinRtOperation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $timer.Stop()
    $rawText = [string]$result.Text
    $bitmap.Dispose()
    $stream.Dispose()

    @{
        schema_version = '1.0'
        status = 'SUCCESS'
        raw_text = $rawText
        engine = 'Windows.Media.Ocr'
        engine_version = 'not_exposed'
        language = $Language
        duration_ms = [int][Math]::Max(0, $timer.ElapsedMilliseconds)
    } | ConvertTo-Json -Compress
    exit 0
}
catch {
    [Console]::Error.WriteLine('ocr adapter failure')
    exit 22
}
