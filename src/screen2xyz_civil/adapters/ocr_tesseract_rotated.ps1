#requires -version 5.1
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,
    [Parameter(Mandatory = $true)]
    [string]$TesseractPath,
    [string]$Angles = "15,20,25",
    [string]$Language = "eng"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$resolvedImage = (Resolve-Path -LiteralPath $ImagePath).Path
$resolvedTesseract = (Resolve-Path -LiteralPath $TesseractPath).Path
$started = [System.Diagnostics.Stopwatch]::StartNew()
$source = $null
$temporaryFiles = [System.Collections.Generic.List[string]]::new()
$words = [System.Collections.Generic.List[object]]::new()

function Convert-BackPoint {
    param(
        [double]$X,
        [double]$Y,
        [double]$CenterX,
        [double]$CenterY,
        [double]$Cosine,
        [double]$Sine
    )
    $deltaX = $X - $CenterX
    $deltaY = $Y - $CenterY
    return [pscustomobject]@{
        X = $CenterX + ($Cosine * $deltaX) + ($Sine * $deltaY)
        Y = $CenterY - ($Sine * $deltaX) + ($Cosine * $deltaY)
    }
}

try {
    $source = [System.Drawing.Image]::FromFile($resolvedImage)
    $centerX = $source.Width / 2.0
    $centerY = $source.Height / 2.0
    foreach ($angleText in ($Angles -split ",")) {
        $angle = [double]::Parse(
            $angleText.Trim(),
            [System.Globalization.CultureInfo]::InvariantCulture
        )
        $bitmap = [System.Drawing.Bitmap]::new($source.Width, $source.Height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.Color]::White)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.TranslateTransform([single]$centerX, [single]$centerY)
            $graphics.RotateTransform([single]$angle)
            $graphics.TranslateTransform([single]-$centerX, [single]-$centerY)
            $graphics.DrawImage($source, 0, 0)
            $tempPath = Join-Path (
                [System.IO.Path]::GetTempPath()
            ) ("screen2xyz-ocr-{0}-{1}.png" -f [guid]::NewGuid(), $angle)
            $bitmap.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
            $temporaryFiles.Add($tempPath)
        }
        finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }

        $radians = $angle * [Math]::PI / 180.0
        $cosine = [Math]::Cos($radians)
        $sine = [Math]::Sin($radians)
        $tsv = & $resolvedTesseract $tempPath stdout --psm 11 -l $Language tsv 2>$null
        foreach ($line in $tsv) {
            $parts = $line -split "`t", -1
            if ($parts.Count -lt 12 -or $parts[0] -ne "5") {
                continue
            }
            $text = $parts[11].Trim()
            if ([string]::IsNullOrWhiteSpace($text)) {
                continue
            }
            $confidence = 0.0
            if (-not [double]::TryParse(
                $parts[10],
                [System.Globalization.NumberStyles]::Float,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [ref]$confidence
            )) {
                continue
            }
            if ($confidence -lt 0) {
                continue
            }
            $left = [double]$parts[6]
            $top = [double]$parts[7]
            $right = $left + [double]$parts[8]
            $bottom = $top + [double]$parts[9]
            $mapped = @(
                (Convert-BackPoint $left $top $centerX $centerY $cosine $sine),
                (Convert-BackPoint $right $top $centerX $centerY $cosine $sine),
                (Convert-BackPoint $right $bottom $centerX $centerY $cosine $sine),
                (Convert-BackPoint $left $bottom $centerX $centerY $cosine $sine)
            )
            $mappedX = @($mapped | ForEach-Object { $_.X })
            $mappedY = @($mapped | ForEach-Object { $_.Y })
            $x0 = [Math]::Max(0.0, ($mappedX | Measure-Object -Minimum).Minimum)
            $y0 = [Math]::Max(0.0, ($mappedY | Measure-Object -Minimum).Minimum)
            $x1 = [Math]::Min(
                [double]$source.Width,
                ($mappedX | Measure-Object -Maximum).Maximum
            )
            $y1 = [Math]::Min(
                [double]$source.Height,
                ($mappedY | Measure-Object -Maximum).Maximum
            )
            if ($x1 -le $x0 -or $y1 -le $y0) {
                continue
            }
            $words.Add([ordered]@{
                text = $text
                x = $x0
                y = $y0
                width = $x1 - $x0
                height = $y1 - $y0
                confidence = [Math]::Min(1.0, $confidence / 100.0)
                angle = $angle
            })
        }
    }
    $started.Stop()
    $payload = [ordered]@{
        schema_version = "1.0"
        status = "SUCCESS"
        engine = "tesseract-multirotation"
        language = $Language
        duration_ms = [int]$started.ElapsedMilliseconds
        raw_text = ($words | ForEach-Object { $_.text }) -join "`n"
        lines = @(
            $words | ForEach-Object {
                [ordered]@{
                    text = $_.text
                    words = @(
                        [ordered]@{
                            text = $_.text
                            x = $_.x
                            y = $_.y
                            width = $_.width
                            height = $_.height
                            confidence = $_.confidence
                        }
                    )
                }
            }
        )
    }
    $payload | ConvertTo-Json -Depth 8 -Compress
}
finally {
    if ($source -ne $null) {
        $source.Dispose()
    }
    foreach ($temporaryFile in $temporaryFiles) {
        Remove-Item -LiteralPath $temporaryFile -Force -ErrorAction SilentlyContinue
    }
}
