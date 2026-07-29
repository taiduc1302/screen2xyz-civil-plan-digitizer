# DISPOSABLE M2-001 PLANNING-GATE HELPER — NOT PRODUCTION CODE.
# Performs exactly one client-area capture using one documented MVP backend.
param(
    [Parameter(Mandatory = $true)][long]$Hwnd,
    [Parameter(Mandatory = $true)][uint32]$ExpectedPid,
    [Parameter(Mandatory = $true)]
    [ValidateSet('copyfromscreen', 'printwindow_clientonly')]
    [string]$Mode,
    [Parameter(Mandatory = $true)][string]$OutPath
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace S7Gate -Name Win32 -MemberDefinition @'
[DllImport("user32.dll", SetLastError = true)]
[return: MarshalAs(UnmanagedType.Bool)]
public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
[DllImport("user32.dll")]
[return: MarshalAs(UnmanagedType.Bool)]
public static extern bool IsWindow(IntPtr hWnd);
[DllImport("user32.dll")]
[return: MarshalAs(UnmanagedType.Bool)]
public static extern bool IsWindowVisible(IntPtr hWnd);
[DllImport("user32.dll")]
[return: MarshalAs(UnmanagedType.Bool)]
public static extern bool IsIconic(IntPtr hWnd);
[DllImport("user32.dll", SetLastError = true)]
[return: MarshalAs(UnmanagedType.Bool)]
public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);
[DllImport("user32.dll", SetLastError = true)]
[return: MarshalAs(UnmanagedType.Bool)]
public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);
[DllImport("user32.dll", SetLastError = true)]
[return: MarshalAs(UnmanagedType.Bool)]
public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
[DllImport("user32.dll", SetLastError = true)]
public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
[DllImport("user32.dll")]
public static extern uint GetDpiForWindow(IntPtr hWnd);
public struct RECT { public int Left, Top, Right, Bottom; }
public struct POINT { public int X, Y; }
'@

if (-not [S7Gate.Win32]::SetProcessDpiAwarenessContext([IntPtr](-4))) {
    [Console]::Error.WriteLine('PMv2 initialization failed')
    exit 21
}

$resolvedOutPath = [System.IO.Path]::GetFullPath($OutPath)
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\') + '\'
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$ignoredGateRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $repositoryRoot '.lab_work\m2_research\s7_preview')
).TrimEnd('\') + '\'
$isTemporary = $resolvedOutPath.StartsWith(
    $tempRoot,
    [System.StringComparison]::OrdinalIgnoreCase
)
$isIgnoredGateOutput = $resolvedOutPath.StartsWith(
    $ignoredGateRoot,
    [System.StringComparison]::OrdinalIgnoreCase
)
if ((-not $isTemporary -and -not $isIgnoredGateOutput) -or
    [System.IO.Path]::GetExtension($resolvedOutPath) -ne '.png') {
    [Console]::Error.WriteLine('output must be a PNG under the OS temporary root or ignored S7 preview root')
    exit 27
}
if (Test-Path -LiteralPath $resolvedOutPath) {
    [Console]::Error.WriteLine('refusing to overwrite an existing output')
    exit 28
}
$OutPath = $resolvedOutPath

$hwnd = [IntPtr]$Hwnd
if ($hwnd -eq [IntPtr]::Zero -or -not [S7Gate.Win32]::IsWindow($hwnd)) {
    [Console]::Error.WriteLine('invalid hwnd')
    exit 20
}
if ((-not [S7Gate.Win32]::IsWindowVisible($hwnd)) -or
    [S7Gate.Win32]::IsIconic($hwnd)) {
    [Console]::Error.WriteLine('target is hidden or minimized')
    exit 32
}
$actualPid = [uint32]0
$threadId = [S7Gate.Win32]::GetWindowThreadProcessId($hwnd, [ref]$actualPid)
if ($threadId -eq 0 -or $actualPid -eq 0 -or $actualPid -ne $ExpectedPid) {
    [Console]::Error.WriteLine('target HWND/PID identity mismatch')
    exit 30
}
$windowDpi = [S7Gate.Win32]::GetDpiForWindow($hwnd)
if ($windowDpi -eq 0) {
    [Console]::Error.WriteLine('GetDpiForWindow returned 0')
    exit 29
}

$rect = New-Object S7Gate.Win32+RECT
if (-not [S7Gate.Win32]::GetClientRect($hwnd, [ref]$rect)) {
    [Console]::Error.WriteLine('GetClientRect failed')
    exit 22
}
$origin = New-Object S7Gate.Win32+POINT
if (-not [S7Gate.Win32]::ClientToScreen($hwnd, [ref]$origin)) {
    [Console]::Error.WriteLine('ClientToScreen failed')
    exit 22
}
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
if ($w -le 0 -or $h -le 0 -or $w -gt 8192 -or $h -gt 8192) {
    [Console]::Error.WriteLine('client dimensions outside planning-gate bounds')
    exit 23
}

$bitmap = $null
$graphics = $null
$hdc = [IntPtr]::Zero
$stagingPath = $null
try {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $bitmap = New-Object System.Drawing.Bitmap $w, $h
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    if ($Mode -eq 'copyfromscreen') {
        try {
            $graphics.CopyFromScreen(
                $origin.X,
                $origin.Y,
                0,
                0,
                (New-Object System.Drawing.Size $w, $h)
            )
        } catch {
            [Console]::Error.WriteLine('CopyFromScreen capture API failed')
            exit 24
        }
    } else {
        $hdc = $graphics.GetHdc()
        if (-not [S7Gate.Win32]::PrintWindow($hwnd, $hdc, [uint32]1)) {
            [Console]::Error.WriteLine('PrintWindow(PW_CLIENTONLY) returned false')
            exit 24
        }
        $graphics.ReleaseHdc($hdc)
        $hdc = [IntPtr]::Zero
    }
    $captureMs = $sw.ElapsedMilliseconds

    $sum = 0.0
    $count = 0
    $minLuma = 255.0
    $maxLuma = 0.0
    $stepY = [Math]::Max(1, [int][Math]::Ceiling($h / 40.0))
    $stepX = [Math]::Max(1, [int][Math]::Ceiling($w / 40.0))
    for ($y = 0; $y -lt $h; $y += $stepY) {
        for ($x = 0; $x -lt $w; $x += $stepX) {
            $p = $bitmap.GetPixel($x, $y)
            $luma = 0.299 * $p.R + 0.587 * $p.G + 0.114 * $p.B
            $sum += $luma
            $minLuma = [Math]::Min($minLuma, $luma)
            $maxLuma = [Math]::Max($maxLuma, $luma)
            $count++
        }
    }
    $meanLuma = $sum / [Math]::Max(1, $count)
    $lumaRange = $maxLuma - $minLuma
    $contentStatus = 'CONTENT_DETECTED'
    if ($lumaRange -le 3.0) {
        if ($meanLuma -le 5.0) {
            $contentStatus = 'NEAR_UNIFORM_DARK'
        } elseif ($meanLuma -ge 250.0) {
            $contentStatus = 'NEAR_UNIFORM_LIGHT'
        } else {
            $contentStatus = 'NEAR_UNIFORM_OTHER'
        }
    }

    # Fail the finite trial if the selected target changed while the blocking
    # capture call was in progress. No result PNG is published in that case.
    $actualPidAfter = [uint32]0
    if ((-not [S7Gate.Win32]::IsWindow($hwnd)) -or
        (-not [S7Gate.Win32]::IsWindowVisible($hwnd)) -or
        [S7Gate.Win32]::IsIconic($hwnd)) {
        [Console]::Error.WriteLine('target became unavailable, hidden, or minimized during capture')
        exit 32
    }
    $threadIdAfter = [S7Gate.Win32]::GetWindowThreadProcessId($hwnd, [ref]$actualPidAfter)
    $windowDpiAfter = [S7Gate.Win32]::GetDpiForWindow($hwnd)
    $rectAfter = New-Object S7Gate.Win32+RECT
    $originAfter = New-Object S7Gate.Win32+POINT
    if ($threadIdAfter -eq 0 -or $actualPidAfter -ne $ExpectedPid) {
        [Console]::Error.WriteLine('target HWND/PID identity changed during capture')
        exit 30
    }
    if ($windowDpiAfter -eq 0 -or $windowDpiAfter -ne $windowDpi) {
        [Console]::Error.WriteLine('target DPI changed during capture')
        exit 29
    }
    if ((-not [S7Gate.Win32]::GetClientRect($hwnd, [ref]$rectAfter)) -or
        (-not [S7Gate.Win32]::ClientToScreen($hwnd, [ref]$originAfter)) -or
        ($rectAfter.Right - $rectAfter.Left -ne $w) -or
        ($rectAfter.Bottom - $rectAfter.Top -ne $h) -or
        ($originAfter.X -ne $origin.X) -or
        ($originAfter.Y -ne $origin.Y)) {
        [Console]::Error.WriteLine('target client geometry changed during capture')
        exit 31
    }

    $parent = Split-Path -Parent $OutPath
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        [void][System.IO.Directory]::CreateDirectory($parent)
    }
    $stagingPath = $OutPath + '.partial-' + $PID + '-' + [guid]::NewGuid().ToString('N')
    $bitmap.Save($stagingPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngBytes = (Get-Item -LiteralPath $stagingPath).Length
    if ($pngBytes -gt 64MB) {
        Remove-Item -LiteralPath $stagingPath -Force
        [Console]::Error.WriteLine('full-frame PNG exceeds 64 MiB planning-gate bound')
        exit 26
    }
    [System.IO.File]::Move($stagingPath, $OutPath)
    $stagingPath = $null
    $result = [ordered]@{
        backend = $Mode
        w = $w
        h = $h
        origin_x = $origin.X
        origin_y = $origin.Y
        window_dpi = $windowDpi
        capture_ms = $captureMs
        sample_count = $count
        mean_luma = [Math]::Round($meanLuma, 2)
        luma_range = [Math]::Round($lumaRange, 2)
        frame_content_status = $contentStatus
        png_bytes = $pngBytes
    }
    [Console]::Out.WriteLine(($result | ConvertTo-Json -Compress))
} catch {
    if ($stagingPath -ne $null -and (Test-Path -LiteralPath $stagingPath)) {
        Remove-Item -LiteralPath $stagingPath -Force
    }
    if (Test-Path -LiteralPath $OutPath) {
        Remove-Item -LiteralPath $OutPath -Force
    }
    [Console]::Error.WriteLine(('capture failed: {0}' -f $_.Exception.GetType().Name))
    exit 25
} finally {
    if ($stagingPath -ne $null -and (Test-Path -LiteralPath $stagingPath)) {
        Remove-Item -LiteralPath $stagingPath -Force
    }
    if ($hdc -ne [IntPtr]::Zero -and $graphics -ne $null) {
        $graphics.ReleaseHdc($hdc)
    }
    if ($graphics -ne $null) { $graphics.Dispose() }
    if ($bitmap -ne $null) { $bitmap.Dispose() }
}

exit 0
