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
    if ($null -eq $payload.jobs -or @($payload.jobs).Count -ne 60) { exit 20 }

    Add-Type -AssemblyName System.Drawing
    $rendered = 0
    foreach ($job in @($payload.jobs)) {
        if ($job.scenario_id -notmatch '^S[0-9]{3}$') { exit 20 }
        $relative = [string]$job.image_relpath
        if ([System.IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)' -or -not $relative.EndsWith('.png')) { exit 20 }
        $target = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($root, $relative))
        if (-not $target.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { exit 20 }
        if ([System.IO.File]::Exists($target)) { exit 21 }
        [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($target)) | Out-Null

        $bitmap = New-Object System.Drawing.Bitmap 1600, 260
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $font = $null
        $brush = $null
        try {
            $bitmap.SetResolution(96, 96)
            $graphics.Clear([System.Drawing.Color]::White)
            $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $font = New-Object System.Drawing.Font('Arial', [single]$job.font_size_px, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
            if ($font.Name -ne 'Arial' -or $font.OriginalFontName -ne 'Arial') { throw 'font substitution detected' }
            $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
            $graphics.DrawString([string]$job.visible_text, $font, $brush, [single]30, [single]80)
            $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
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
    [Console]::Error.WriteLine('renderer failure')
    exit 21
}
