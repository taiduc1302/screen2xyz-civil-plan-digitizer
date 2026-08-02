param(
    [Parameter(Mandatory = $true)][string]$RenderJobsPath,
    [Parameter(Mandatory = $true)][string]$OutputRoot
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

try {
    $jobsPath = [System.IO.Path]::GetFullPath($RenderJobsPath)
    $root = [System.IO.Path]::GetFullPath($OutputRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    if (-not [System.IO.File]::Exists($jobsPath)) { exit 20 }
    $payload = [System.IO.File]::ReadAllText($jobsPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($null -eq $payload.jobs -or @($payload.jobs).Count -lt 1 -or @($payload.jobs).Count -gt 200) { exit 20 }

    Add-Type -AssemblyName System.Drawing
    $rendered = 0
    foreach ($job in @($payload.jobs)) {
        if ($job.scenario_id -notmatch '^M[0-9]{3}$') { exit 20 }
        $relative = [string]$job.image_relpath
        if ([System.IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)' -or -not $relative.EndsWith('.png')) { exit 20 }
        $target = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($root, $relative))
        if (-not $target.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { exit 20 }
        if ([System.IO.File]::Exists($target)) { exit 21 }
        [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($target)) | Out-Null

        $width = [int]$job.width_px
        $height = [int]$job.height_px
        if ($width -lt 100 -or $width -gt 4000 -or $height -lt 60 -or $height -gt 2000) { exit 20 }
        $gray = [int]$job.foreground_gray
        $bg = [int]$job.background_gray
        if ($gray -lt 0 -or $gray -gt 255 -or $bg -lt 0 -or $bg -gt 255) { exit 20 }
        $scale = [double]$job.softness_scale
        if ($scale -lt 0.4 -or $scale -gt 1.0) { exit 20 }

        $bitmap = New-Object System.Drawing.Bitmap $width, $height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $font = $null
        $brush = $null
        try {
            $bitmap.SetResolution(96, 96)
            $graphics.Clear([System.Drawing.Color]::FromArgb($bg, $bg, $bg))
            $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
            $font = New-Object System.Drawing.Font('Arial', [single]$job.font_size_px, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
            if ($font.Name -ne 'Arial') { throw 'font substitution detected' }
            $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($gray, $gray, $gray))
            foreach ($line in @($job.lines)) {
                $graphics.DrawString([string]$line.text, $font, $brush, [single]$line.x, [single]$line.y)
            }
            if ($scale -lt 1.0) {
                # Downscale then upscale to soften glyph edges deterministically.
                $smallWidth = [Math]::Max(1, [int]($width * $scale))
                $smallHeight = [Math]::Max(1, [int]($height * $scale))
                $small = New-Object System.Drawing.Bitmap $smallWidth, $smallHeight
                $final = New-Object System.Drawing.Bitmap $width, $height
                try {
                    $gSmall = [System.Drawing.Graphics]::FromImage($small)
                    $gFinal = [System.Drawing.Graphics]::FromImage($final)
                    try {
                        $gSmall.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBilinear
                        $gFinal.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBilinear
                        $gSmall.DrawImage($bitmap, 0, 0, $smallWidth, $smallHeight)
                        $gFinal.DrawImage($small, 0, 0, $width, $height)
                    }
                    finally {
                        $gSmall.Dispose()
                        $gFinal.Dispose()
                    }
                    $final.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
                }
                finally {
                    $small.Dispose()
                    $final.Dispose()
                }
            }
            else {
                $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
            }
        }
        finally {
            if ($null -ne $brush) { $brush.Dispose() }
            if ($null -ne $font) { $font.Dispose() }
            $graphics.Dispose()
            $bitmap.Dispose()
        }
        $rendered++
    }
    @{ schema_version = '1.0'; status = 'SUCCESS'; rendered_count = $rendered } | ConvertTo-Json -Compress
    exit 0
}
catch {
    [Console]::Error.WriteLine('m1 renderer failure')
    exit 21
}
