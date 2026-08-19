# Screen2XYZ M2 long-lived capture/OCR worker. Protocol m2w.1 (JSON lines).
# stdout carries protocol replies only; stderr carries diagnostics only.
# The worker exits when stdin closes or its parent process dies.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# Under CREATE_NO_WINDOW the process has no console; setting the console
# encodings then throws. Guard both and fall back to the PS output pipeline,
# which is already UTF-8 via our JSON (ASCII-safe by default).
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
try { [Console]::OutputEncoding = $Utf8NoBom } catch {}
try { [Console]::InputEncoding = $Utf8NoBom } catch {}
$OutputEncoding = $Utf8NoBom

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace M2 -Name Win32 -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
[DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);
[DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);
[DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr hWnd, ref POINT point);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
[DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
[DllImport("user32.dll")] public static extern int GetDpiForWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT point);
public struct RECT { public int Left, Top, Right, Bottom; }
public struct POINT { public int X, Y; }

// PrintWindow has been observed to hang indefinitely against some
// DWM-layered/composited real windows (not just return blank content), which
// would otherwise stall this worker's single-threaded synchronous protocol
// loop forever. Running it on a background thread and joining with a bound
// keeps a hang from ever blocking the caller past timeoutMs. This is plain
// C# with no PowerShell scriptblock crossing the thread boundary - a raw
// System.Threading.Thread has no PowerShell runspace, so a PS scriptblock
// as its body is unsafe (can crash the host); a pure P/Invoke call is not.
public static bool TryPrintWindowBounded(IntPtr hWnd, IntPtr hdc, uint flags,
                                         int timeoutMs, out bool timedOut) {
    bool result = false;
    System.Threading.Thread t = new System.Threading.Thread(delegate() {
        try { result = PrintWindow(hWnd, hdc, flags); } catch { }
    });
    t.IsBackground = true;
    t.Start();
    bool finished = t.Join(timeoutMs);
    timedOut = !finished;
    return result;
}
'@

# PMv2 before any window/DC call (mixed-DPI correctness lives here).
$pmv2 = [M2.Win32]::SetProcessDpiAwarenessContext([IntPtr]::op_Explicit(-4))
$script:DpiAwareness = if ($pmv2) { 'per_monitor_v2' } else { 'unknown' }

function Await-Op {
    param($Operation, [Type]$ResultType)
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]

$MiB = 1048576
$CROP_PNG_MAX = 8 * $MiB
$FULL_FRAME_MAX = 64 * $MiB
$AGG_CROP_MAX = 64 * $MiB
$REQUEST_LINE_MAX = 1 * $MiB
$PRINTWINDOW_TIMEOUT_MS = 1500
# A timed-out PrintWindow call's background thread may still be inside the
# native call using this exact bitmap/HDC; disposing or finalizing them while
# that native call is in flight is a use-after-free/race risk. Keep a hard
# reference so the CLR never garbage-collects/finalizes them - a bounded,
# rare leak (at most one per session, since the effective backend then
# latches away from PrintWindow) is safer than a crash.
$script:AbandonedCaptures = New-Object System.Collections.ArrayList

$script:Mode = 'SETUP'
$script:Generation = ''
$script:Revision = -1
$script:PreviewedRevision = -1
$script:SessionId = ''
$script:Scope = $null
$script:Backend = 'printwindow_clientonly'
# When $script:Backend is 'auto', $script:EffectiveBackend holds the backend
# a probe has actually latched onto; $null means not yet resolved. Explicit
# (non-auto) backends never populate this - they are used directly every time.
$script:EffectiveBackend = $null
$script:UsableContentStatuses = @('CONTENT_DETECTED', 'NEAR_UNIFORM_OTHER')
$script:CursorMeta = $false
$script:Engine = $null
$script:Sha = [System.Security.Cryptography.SHA256]::Create()

function Write-Reply { param($Object)
    [Console]::Out.WriteLine((ConvertTo-Json -InputObject $Object -Compress -Depth 12))
}
function Write-Diag { param([string]$Text)
    [Console]::Error.WriteLine($Text)
}

function Start-ParentWatch { param([int]$ParentProcessId)
    # Orphan prevention is handled by two mechanisms that do NOT touch the
    # synchronous stdin/stdout loop: (1) stdin closing on parent death makes
    # ReadLine return null and the worker exits (measured <1s in S6);
    # (2) the Python client assigns this process to a kill-on-job-close Job
    # object. A PowerShell-side timer/event was removed because its Action
    # runs on the PS event queue and intermittently stalled the capture loop.
    # This function only validates the parent exists at startup (once,
    # avoiding the documented PID-reuse race) and otherwise does nothing.
    if ($ParentProcessId -le 0) { return }
    try { $null = [System.Diagnostics.Process]::GetProcessById($ParentProcessId) }
    catch { Write-Diag 'parent already gone'; [Environment]::Exit(0) }
}

function Get-WindowInfo { param([long]$Hwnd)
    $handle = [IntPtr]$Hwnd
    $info = @{ exists = $false; iconic = $false; client_w = 0; client_h = 0
               origin_x = 0; origin_y = 0; dpi = 0 }
    if (-not [M2.Win32]::IsWindow($handle)) { return $info }
    $info.exists = $true
    $info.iconic = [bool][M2.Win32]::IsIconic($handle)
    $rect = New-Object M2.Win32+RECT
    if ([M2.Win32]::GetClientRect($handle, [ref]$rect)) {
        $info.client_w = $rect.Right; $info.client_h = $rect.Bottom
        $point = New-Object M2.Win32+POINT
        [void][M2.Win32]::ClientToScreen($handle, [ref]$point)
        $info.origin_x = $point.X; $info.origin_y = $point.Y
        $info.dpi = [M2.Win32]::GetDpiForWindow($handle)
    }
    return $info
}

function Test-WindowIdentity { param([long]$Hwnd, [int]$ExpectedProcessId)
    $processId = [uint32]0
    [void][M2.Win32]::GetWindowThreadProcessId([IntPtr]$Hwnd, [ref]$processId)
    return ($processId -eq [uint32]$ExpectedProcessId)
}

function Capture-Frame {
    # Returns @{ ok; bitmap; window; capture_ms; error }. $Backend selects the
    # GDI method for a window-scope capture; monitor scope always visits the
    # CopyFromScreen branch below regardless of $Backend (there is no
    # PrintWindow target - a monitor is not a window).
    param([string]$Backend)
    $scope = $script:Scope
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    if ($scope.type -eq 'window') {
        $info = Get-WindowInfo -Hwnd $scope.hwnd
        if (-not $info.exists -or -not (Test-WindowIdentity -Hwnd $scope.hwnd -ExpectedProcessId $scope.pid)) {
            return @{ ok = $false; error = 'TARGET_UNAVAILABLE'; window = $info }
        }
        if ($info.iconic) {
            return @{ ok = $false; error = 'TARGET_MINIMIZED'; window = $info }
        }
        if ($info.client_w -le 0 -or $info.client_h -le 0 -or
            $info.client_w -gt 8192 -or $info.client_h -gt 8192) {
            return @{ ok = $false; error = 'BACKEND_FAILURE'; window = $info }
        }
        $bitmap = New-Object System.Drawing.Bitmap $info.client_w, $info.client_h
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        if ($Backend -eq 'printwindow_clientonly') {
            $hdc = $graphics.GetHdc()
            $timedOut = $false
            $ok = [M2.Win32]::TryPrintWindowBounded([IntPtr]$scope.hwnd, $hdc,
                [uint32]1, $PRINTWINDOW_TIMEOUT_MS, [ref]$timedOut)
            if ($timedOut) {
                # The background call may still be running against this exact
                # HDC; releasing it or disposing $bitmap/$graphics now would
                # race a native GDI call in flight. Abandon them (kept alive
                # in $script:AbandonedCaptures, never disposed) instead.
                Write-Diag "PrintWindow timed out after $PRINTWINDOW_TIMEOUT_MS ms; abandoning this attempt"
                [void]$script:AbandonedCaptures.Add(@{ bitmap = $bitmap; graphics = $graphics })
                return @{ ok = $false; error = 'BACKEND_FAILURE'; window = $info; timed_out = $true }
            }
            $graphics.ReleaseHdc($hdc)
            $graphics.Dispose()
            if (-not $ok) {
                $bitmap.Dispose()
                return @{ ok = $false; error = 'BACKEND_FAILURE'; window = $info }
            }
        } else {
            try {
                $graphics.CopyFromScreen($info.origin_x, $info.origin_y, 0, 0,
                    (New-Object System.Drawing.Size $info.client_w, $info.client_h))
            } catch {
                $graphics.Dispose()
                $bitmap.Dispose()
                return @{ ok = $false; error = 'BACKEND_FAILURE'; window = $info }
            }
            $graphics.Dispose()
        }
        return @{ ok = $true; bitmap = $bitmap; window = $info
                  capture_ms = [int]$sw.ElapsedMilliseconds }
    }
    # monitor scope: visible pixels of the selected monitor rectangle
    $m = $scope.monitor
    $bitmap = New-Object System.Drawing.Bitmap $m.w, $m.h
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try { $graphics.CopyFromScreen($m.x, $m.y, 0, 0, (New-Object System.Drawing.Size $m.w, $m.h)) }
    catch { $bitmap.Dispose(); return @{ ok = $false; error = 'BACKEND_FAILURE'
             window = @{ exists = $true; iconic = $false; client_w = $m.w; client_h = $m.h
                         origin_x = $m.x; origin_y = $m.y; dpi = 96 } } }
    finally { $graphics.Dispose() }
    return @{ ok = $true; bitmap = $bitmap
              window = @{ exists = $true; iconic = $false; client_w = $m.w; client_h = $m.h
                          origin_x = $m.x; origin_y = $m.y; dpi = 96 }
              capture_ms = [int]$sw.ElapsedMilliseconds }
}

function Test-FrameUsable { param([string]$ContentStatus)
    return $script:UsableContentStatuses -contains $ContentStatus
}

function Resolve-And-Capture {
    # Wraps Capture-Frame with real Auto-backend resolution. Adds
    # backend_used (string), probe_results (array or $null - only populated
    # when a probe actually ran this call) and no_backend_usable (bool) to
    # the returned frame hashtable.
    param([bool]$ForceProbe)
    if ($script:Scope.type -ne 'window') {
        # Monitor scope has no PrintWindow target; CopyFromScreen is the only
        # option and is already what Capture-Frame does for it.
        $frame = Capture-Frame -Backend 'copyfromscreen'
        $frame.backend_used = 'copyfromscreen'
        $frame.probe_results = $null
        $frame.no_backend_usable = $false
        return $frame
    }
    if ($script:Backend -ne 'auto') {
        $frame = Capture-Frame -Backend $script:Backend
        $frame.backend_used = $script:Backend
        $frame.probe_results = $null
        $frame.no_backend_usable = $false
        return $frame
    }
    if ($script:EffectiveBackend -and -not $ForceProbe) {
        # Already resolved: use it directly. This is what keeps every
        # RECORDING tick to a single capture - Auto never re-probes per tick.
        $frame = Capture-Frame -Backend $script:EffectiveBackend
        $frame.backend_used = $script:EffectiveBackend
        $frame.probe_results = $null
        $frame.no_backend_usable = $false
        return $frame
    }
    # Fresh resolution (first use, or an explicit Retest): try PrintWindow
    # first (cheap, no visibility requirement), classify the real pixels,
    # and fall back to CopyFromScreen only when PrintWindow's frame is not
    # usable (near-uniform dark/light is the exact failure the owner's real
    # target showed).
    $probe = @()
    $pw = Capture-Frame -Backend 'printwindow_clientonly'
    $pwStatus = if ($pw.ok) { Get-ContentStatus -Bitmap $pw.bitmap } else { 'CAPTURE_FAILED' }
    $pwUsable = $pw.ok -and (Test-FrameUsable $pwStatus)
    $probe += @{ backend = 'printwindow_clientonly'; content_status = $pwStatus
                 usable = $pwUsable
                 capture_ms = $(if ($pw.ok) { $pw.capture_ms } else { 0 }) }
    if ($pwUsable) {
        $script:EffectiveBackend = 'printwindow_clientonly'
        $pw.backend_used = 'printwindow_clientonly'
        $pw.probe_results = $probe
        $pw.no_backend_usable = $false
        return $pw
    }
    if ($pw.ok -and $pw.bitmap) { $pw.bitmap.Dispose() }
    $cs = Capture-Frame -Backend 'copyfromscreen'
    $csStatus = if ($cs.ok) { Get-ContentStatus -Bitmap $cs.bitmap } else { 'CAPTURE_FAILED' }
    $csUsable = $cs.ok -and (Test-FrameUsable $csStatus)
    $probe += @{ backend = 'copyfromscreen'; content_status = $csStatus
                 usable = $csUsable
                 capture_ms = $(if ($cs.ok) { $cs.capture_ms } else { 0 }) }
    # Latch CopyFromScreen either way (usable or not) so a persistently
    # unusable target still costs one capture per tick, not two: the ongoing
    # NEAR_UNIFORM/blank-streak pause logic downstream already reacts to a
    # frame that keeps coming back unusable.
    $script:EffectiveBackend = 'copyfromscreen'
    $cs.backend_used = 'copyfromscreen'
    $cs.probe_results = $probe
    $cs.no_backend_usable = -not $csUsable
    return $cs
}

function Get-ContentStatus { param([System.Drawing.Bitmap]$Bitmap)
    $w = $Bitmap.Width; $h = $Bitmap.Height
    $stepX = [Math]::Max(1, [int]($w / 40)); $stepY = [Math]::Max(1, [int]($h / 40))
    $min = 255.0; $max = 0.0; $sum = 0.0; $count = 0
    for ($y = 0; $y -lt $h; $y += $stepY) {
        for ($x = 0; $x -lt $w; $x += $stepX) {
            $p = $Bitmap.GetPixel($x, $y)
            $luma = 0.299 * $p.R + 0.587 * $p.G + 0.114 * $p.B
            if ($luma -lt $min) { $min = $luma }
            if ($luma -gt $max) { $max = $luma }
            $sum += $luma; $count++
        }
    }
    $mean = if ($count) { $sum / $count } else { 0 }
    if (($max - $min) -le 3.0) {
        if ($mean -le 5.0) { return 'NEAR_UNIFORM_DARK' }
        if ($mean -ge 250.0) { return 'NEAR_UNIFORM_LIGHT' }
        return 'NEAR_UNIFORM_OTHER'
    }
    return 'CONTENT_DETECTED'
}

function Get-PixelHash { param([System.Drawing.Bitmap]$Bitmap)
    $rect = New-Object System.Drawing.Rectangle 0, 0, $Bitmap.Width, $Bitmap.Height
    $data = $Bitmap.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    try {
        $length = $data.Stride * $data.Height
        $bytes = New-Object byte[] $length
        [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $length)
        return ([System.BitConverter]::ToString($script:Sha.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant()
    } finally { $Bitmap.UnlockBits($data) }
}

function Get-PngBytes { param([System.Drawing.Bitmap]$Bitmap)
    $stream = New-Object System.IO.MemoryStream
    $Bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    return $stream.ToArray()
}

function Invoke-Ocr { param([System.Drawing.Bitmap]$Crop, [int]$Upscale)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $work = $Crop
    $padded = $null
    $scaled = $null
    try {
        # Real-target finding (owner test against Google Earth's coordinate
        # readout, 2026-07-19): at native scale (Upscale=1, the field
        # default), Windows.Media.Ocr reliably returns EMPTY TEXT for small
        # on-screen UI text - confirmed empirically with a standalone
        # RecognizeAsync harness against ~13pt text crops ~24px tall: EVERY
        # variant tested (busy photographic background, plain background,
        # fully opaque high-contrast, and even the textbook dark-text-on-
        # light-background control case) returned nothing at 1x, and EVERY
        # variant recognized the text correctly once upscaled >=2x. So this
        # is not about contrast, background, or light-on-dark text - it is
        # that most single-line UI text (status bars, HUD overlays, small
        # labels) renders shorter than Windows OCR's effective minimum, and
        # the crop clearly shows legible text to a human, making the silent
        # empty result look like an app bug. A crop shorter than this floor
        # is now upscaled at least 3x for OCR regardless of the field's own
        # setting (a safe margin above the empirically-sufficient 2x); an
        # explicitly higher configured upscale is never reduced, and the
        # field's own stored upscale_factor setting is untouched - only the
        # image actually fed to OCR is affected.
        #
        # Second finding, Phase 0 boundary audit (2026-07-19): upscale alone
        # does NOT fix a TIGHTLY-drawn region - which is exactly what the
        # app's own troubleshooting guidance recommended ("redraw the region
        # tighter around just the digits"). A controlled sweep proved
        # padding/margin around the ink, independent of scale, is at least
        # as load-bearing as scale: a 160x22 crop with ~6px margin around
        # short numeric text returned EMPTY at EVERY upscale from 1x-6x with
        # no padding, but succeeded at every scale from 2x once padded by as
        # little as 3-8px, and succeeded even at native 1x (no upscale at
        # all) once padded by >=12px. The same padding fixed the ORIGINAL
        # dark-overlay Google Earth-style crop's remaining 1x failure too.
        # So every crop - not only short ones - is now padded by a fixed
        # margin, sampled from the crop's own near-corner pixel so the
        # border blends in rather than introducing a foreign-coloured edge,
        # BEFORE the existing height-based upscale floor is evaluated.
        $PAD_PX = 16
        $bgColor = $Crop.GetPixel(0, 0)
        $padded = New-Object System.Drawing.Bitmap `
            ($Crop.Width + 2 * $PAD_PX), ($Crop.Height + 2 * $PAD_PX)
        $gp = [System.Drawing.Graphics]::FromImage($padded)
        $gp.Clear($bgColor)
        $gp.DrawImageUnscaled($Crop, $PAD_PX, $PAD_PX)
        $gp.Dispose()
        $work = $padded

        $effectiveUpscale = $Upscale
        if ($Crop.Height -lt 60 -and $effectiveUpscale -lt 3) {
            $effectiveUpscale = 3
        }
        if ($effectiveUpscale -gt 1) {
            $maxDim = [uint32][Windows.Media.Ocr.OcrEngine]::MaxImageDimension
            $newW = $work.Width * $effectiveUpscale; $newH = $work.Height * $effectiveUpscale
            if ($newW -le $maxDim -and $newH -le $maxDim) {
                $scaled = New-Object System.Drawing.Bitmap $newW, $newH
                $g = [System.Drawing.Graphics]::FromImage($scaled)
                $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $g.DrawImage($work, 0, 0, $newW, $newH)
                $g.Dispose()
                $work = $scaled
            } else {
                # Upscale would exceed MaxImageDimension: OCR at padded-but-
                # native size and surface it so the result is never silently
                # different from what the diagnostics imply.
                Write-Diag "upscale skipped: exceeds MaxImageDimension"
            }
        }
        Write-Diag ("ocr: crop=$($Crop.Width)x$($Crop.Height) pad=$PAD_PX " +
                    "effective_upscale=$effectiveUpscale " +
                    "final=$($work.Width)x$($work.Height)")
        $png = Get-PngBytes -Bitmap $work
        $ras = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
        $writer = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForWrite($ras.GetOutputStreamAt(0))
        $writer.Write($png, 0, $png.Length); $writer.Flush(); $writer.Dispose()
        $decoder = Await-Op ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $software = Await-Op ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await-Op ($script:Engine.RecognizeAsync($software)) ([Windows.Media.Ocr.OcrResult])
        $software.Dispose(); $ras.Dispose()
        # Windows.Media.Ocr can occasionally return EMPTY_TEXT for a
        # content-bearing small live-window crop.  Retry only that safe
        # failure with one larger rendition of the same immutable pixels;
        # non-empty reads are never replaced or silently reinterpreted.
        if ($result.Text.Trim().Length -eq 0 -and $effectiveUpscale -lt 4) {
            foreach ($retryScale in @(4)) {
                $retry = $null; $retryRas = $null; $retrySoftware = $null
                try {
                    $retry = New-Object System.Drawing.Bitmap ($padded.Width * $retryScale), ($padded.Height * $retryScale)
                    $retryGraphics = [System.Drawing.Graphics]::FromImage($retry)
                    $retryGraphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                    $retryGraphics.DrawImage($padded, 0, 0, $retry.Width, $retry.Height)
                    $retryGraphics.Dispose()
                    $retryPng = Get-PngBytes -Bitmap $retry
                    $retryRas = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
                    $retryWriter = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForWrite($retryRas.GetOutputStreamAt(0))
                    $retryWriter.Write($retryPng, 0, $retryPng.Length); $retryWriter.Flush(); $retryWriter.Dispose()
                    $retryDecoder = Await-Op ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($retryRas)) ([Windows.Graphics.Imaging.BitmapDecoder])
                    $retrySoftware = Await-Op ($retryDecoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
                    $retryResult = Await-Op ($script:Engine.RecognizeAsync($retrySoftware)) ([Windows.Media.Ocr.OcrResult])
                    if ($retryResult.Text.Trim().Length -gt 0) {
                        $result = $retryResult
                        break
                    }
                } finally {
                    if ($retrySoftware) { $retrySoftware.Dispose() }
                    if ($retryRas) { $retryRas.Dispose() }
                    if ($retry) { $retry.Dispose() }
                }
            }
        }
        return @{ ok = $true; text = [string]$result.Text; ocr_ms = [int]$sw.ElapsedMilliseconds }
    } catch {
        Write-Diag ("ocr failure: " + $_.Exception.Message)
        return @{ ok = $false; text = ''; ocr_ms = [int]$sw.ElapsedMilliseconds }
    } finally {
        if ($scaled) { $scaled.Dispose() }
        if ($padded) { $padded.Dispose() }
    }
}

function Get-CursorInfo {
    if (-not $script:CursorMeta) { return $null }
    $point = New-Object M2.Win32+POINT
    if (-not [M2.Win32]::GetCursorPos([ref]$point)) { return $null }
    $cursor = @{ screen_x = $point.X; screen_y = $point.Y
                 client_x = $null; client_y = $null }
    if ($script:Scope.type -eq 'window') {
        $client = New-Object M2.Win32+POINT
        $client.X = $point.X; $client.Y = $point.Y
        if ([M2.Win32]::ScreenToClient([IntPtr]$script:Scope.hwnd, [ref]$client)) {
            $cursor.client_x = $client.X; $cursor.client_y = $client.Y
        }
    }
    return $cursor
}

function Fail-Reply { param($Request, [string]$WorkerStatus, [string]$Detail)
    Write-Reply @{ protocol_version = 'm2w.1'
        request_id = $Request.request_id
        worker_generation = $script:Generation
        configuration_revision = $script:Revision
        worker_mode = $script:Mode
        worker_status = $WorkerStatus
        error = $Detail }
}

function Handle-Init { param($Request)
    if ($Request.protocol_version -ne 'm2w.1') {
        Fail-Reply $Request 'PROTOCOL_ERROR' 'protocol version mismatch'
        return $false
    }
    $script:Generation = [string]$Request.worker_generation
    $script:Revision = [int]$Request.configuration_revision
    $script:SessionId = [string]$Request.session_id
    $script:Scope = $Request.scope
    $script:Backend = [string]$Request.backend
    $script:EffectiveBackend = $null
    $script:CursorMeta = [bool]$Request.cursor_metadata
    $language = if ($Request.ocr_language) { [string]$Request.ocr_language } else { 'en-US' }
    $script:Engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage(
        (New-Object Windows.Globalization.Language($language)))
    if ($null -eq $script:Engine) {
        Fail-Reply $Request 'PROTOCOL_ERROR' "no OCR engine for $language"
        return $false
    }
    Start-ParentWatch -ParentProcessId ([int]$Request.parent_pid)
    $restore = [string]$Request.restore_session_state
    $script:Mode = switch ($restore) {
        'ARMED' { 'ARMED' }
        'RECORDING' { 'RECORDING' }
        'PAUSED' { 'PAUSED' }
        default { 'SETUP' }
    }
    $languages = @([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages |
                   ForEach-Object { $_.LanguageTag })
    Write-Reply @{ protocol_version = 'm2w.1'
        request_id = $Request.request_id
        worker_generation = $script:Generation
        configuration_revision = $script:Revision
        worker_mode = $script:Mode
        worker_status = 'OK'
        max_image_dimension = [uint32][Windows.Media.Ocr.OcrEngine]::MaxImageDimension
        available_languages = $languages
        backends = @{ printwindow_clientonly = $true; copyfromscreen = $true; auto = $true }
        dpi_awareness = $script:DpiAwareness
        restore_session_state = $restore
        limits = @{ max_crop_png_bytes = $CROP_PNG_MAX
                    max_aggregate_crop_bytes = $AGG_CROP_MAX
                    max_full_frame_png_bytes = $FULL_FRAME_MAX
                    max_json_line_bytes = 96 * $MiB } }
    return $true
}

function Sync-Envelope { param($Request, [string[]]$SetupCommands)
    # Returns $true when the request may proceed.
    if ([string]$Request.worker_generation -ne $script:Generation) {
        Fail-Reply $Request 'PROTOCOL_ERROR' 'generation mismatch'
        return $false
    }
    $revision = [int]$Request.configuration_revision
    if ($SetupCommands -contains [string]$Request.command) {
        if ($revision -ne $script:Revision) {
            $script:Revision = $revision
            $script:Mode = 'SETUP'
            $script:PreviewedRevision = -1
        }
        return $true
    }
    if ($revision -ne $script:Revision) {
        Fail-Reply $Request 'PROTOCOL_ERROR' 'revision mismatch'
        return $false
    }
    return $true
}

function Build-Observation { param($Region, [System.Drawing.Bitmap]$Frame, [bool]$IsPreview)
    $x = [int]$Region.rect.x; $y = [int]$Region.rect.y
    $w = [int]$Region.rect.w; $h = [int]$Region.rect.h
    $obs = @{ source_id = [string]$Region.source_id
              capture_status = 'OK'; crop_content_status = 'NOT_EVALUATED'
              ocr_status = 'NOT_RUN_CAPTURE_FAILED'
              pixel_sha256 = $null; crop_w = $w; crop_h = $h
              ocr_executed = $false; confirmation = 'new_ocr'
              raw_text = ''; raw_truncated = $false
              raw_original_utf8_bytes = $null; warning_codes = @()
              ocr_ms = 0; crop_png_b64 = $null }
    if ($x -lt 0 -or $y -lt 0 -or ($x + $w) -gt $Frame.Width -or ($y + $h) -gt $Frame.Height) {
        $obs.capture_status = 'REGION_OUT_OF_BOUNDS'
        return $obs
    }
    $crop = $Frame.Clone((New-Object System.Drawing.Rectangle $x, $y, $w, $h),
                         $Frame.PixelFormat)
    try {
        $obs.pixel_sha256 = Get-PixelHash -Bitmap $crop
        $obs.crop_content_status = Get-ContentStatus -Bitmap $crop
        $changed = ($IsPreview -or -not $Region.prev_pixel_sha256 -or
                    [string]$Region.prev_pixel_sha256 -ne $obs.pixel_sha256)
        if (-not $changed) {
            $obs.ocr_status = 'NOT_RUN_UNCHANGED'
            $obs.ocr_executed = $false
            $obs.confirmation = 'pixel_hash_cached'
            return $obs
        }
        $upscale = if ($Region.upscale) { [int]$Region.upscale } else { 1 }
        $ocr = Invoke-Ocr -Crop $crop -Upscale $upscale
        $obs.ocr_ms = $ocr.ocr_ms
        $obs.ocr_executed = $true
        if (-not $ocr.ok) { $obs.ocr_status = 'ENGINE_FAILURE'; return $obs }
        $text = $ocr.text
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
        if ($bytes.Length -gt 4096) {
            $take = 4096
            while ($take -gt 0 -and ($bytes[$take - 1] -band 0xC0) -eq 0x80) { $take-- }
            if ($take -gt 0 -and $bytes[$take - 1] -ge 0xC0) { $take-- }
            $obs.raw_text = [System.Text.Encoding]::UTF8.GetString($bytes, 0, $take)
            $obs.raw_truncated = $true
            $obs.raw_original_utf8_bytes = $bytes.Length
            $obs.warning_codes = @('RAW_OCR_TRUNCATED')
        } else {
            $obs.raw_text = $text
            $obs.raw_original_utf8_bytes = $bytes.Length
        }
        $obs.ocr_status = if ($text.Trim().Length -eq 0) { 'EMPTY_TEXT' } else { 'OK' }
        $png = Get-PngBytes -Bitmap $crop
        if ($png.Length -le $CROP_PNG_MAX) {
            $obs.crop_png_b64 = [Convert]::ToBase64String($png)
        } else {
            $obs.capture_status = 'PAYLOAD_TOO_LARGE'
        }
        return $obs
    } finally { $crop.Dispose() }
}

function Handle-Capture { param($Request, [bool]$IsPreview)
    # RECORDING-loop ticks never force a fresh probe (ForceProbe=$false):
    # Auto resolves once (here or at an earlier PREVIEW/REGION_SNAPSHOT) and
    # then reuses the latched effective backend for the rest of the session.
    $frame = Resolve-And-Capture -ForceProbe $false
    $observations = @()
    if (-not $frame.ok) {
        foreach ($region in @($Request.regions)) {
            $observations += @{ source_id = [string]$region.source_id
                capture_status = $frame.error
                crop_content_status = 'NOT_EVALUATED'
                ocr_status = 'NOT_RUN_CAPTURE_FAILED'
                pixel_sha256 = $null
                crop_w = [int]$region.rect.w; crop_h = [int]$region.rect.h
                ocr_executed = $false; confirmation = 'new_ocr'
                raw_text = ''; raw_truncated = $false
                raw_original_utf8_bytes = $null; warning_codes = @()
                ocr_ms = 0; crop_png_b64 = $null }
        }
        Write-Reply @{ protocol_version = 'm2w.1'
            request_id = $Request.request_id
            worker_generation = $script:Generation
            configuration_revision = $script:Revision
            worker_mode = $script:Mode
            worker_status = 'OK'
            frame_seq = $Request.frame_seq
            capture_utc = (Get-Date).ToUniversalTime().ToString('o')
            window = $frame.window
            capture_status = $frame.error
            frame_content_status = 'NOT_EVALUATED'
            cursor = (Get-CursorInfo)
            effective_backend = $frame.backend_used
            backend_probe = $frame.probe_results
            no_backend_usable = [bool]$frame.no_backend_usable
            timings = @{ capture_ms = 0; ocr_ms_total = 0 }
            observations = $observations }
        return
    }
    $bitmap = $frame.bitmap
    try {
        $frameStatus = Get-ContentStatus -Bitmap $bitmap
        $ocrTotal = 0
        $aggregate = 0
        foreach ($region in @($Request.regions)) {
            $obs = Build-Observation -Region $region -Frame $bitmap -IsPreview $IsPreview
            $ocrTotal += [int]$obs.ocr_ms
            if ($obs.crop_png_b64) {
                $aggregate += [int]([Math]::Floor($obs.crop_png_b64.Length * 3 / 4))
                if ($aggregate -gt $AGG_CROP_MAX) {
                    $obs.crop_png_b64 = $null
                    $obs.capture_status = 'PAYLOAD_TOO_LARGE'
                }
            }
            $observations += $obs
        }
        Write-Reply @{ protocol_version = 'm2w.1'
            request_id = $Request.request_id
            worker_generation = $script:Generation
            configuration_revision = $script:Revision
            worker_mode = $script:Mode
            worker_status = 'OK'
            frame_seq = $Request.frame_seq
            capture_utc = (Get-Date).ToUniversalTime().ToString('o')
            window = $frame.window
            capture_status = 'OK'
            frame_content_status = $frameStatus
            cursor = (Get-CursorInfo)
            effective_backend = $frame.backend_used
            backend_probe = $frame.probe_results
            no_backend_usable = [bool]$frame.no_backend_usable
            timings = @{ capture_ms = $frame.capture_ms; ocr_ms_total = $ocrTotal }
            observations = $observations }
    } finally { $bitmap.Dispose() }
}

function Handle-Snapshot { param($Request, [bool]$ForceProbe)
    # Test capture / Retest force a fresh Auto resolution; a plain region
    # snapshot taken after resolution just reuses the latched backend.
    $frame = Resolve-And-Capture -ForceProbe $ForceProbe
    if (-not $frame.ok) {
        Write-Reply @{ protocol_version = 'm2w.1'
            request_id = $Request.request_id
            worker_generation = $script:Generation
            configuration_revision = $script:Revision
            worker_mode = $script:Mode
            worker_status = 'OK'
            capture_status = $frame.error
            window = $frame.window
            frame_content_status = 'NOT_EVALUATED'
            effective_backend = $frame.backend_used
            backend_probe = $frame.probe_results
            no_backend_usable = [bool]$frame.no_backend_usable
            frame_png_b64 = $null }
        return
    }
    $bitmap = $frame.bitmap
    try {
        $png = Get-PngBytes -Bitmap $bitmap
        $b64 = $null
        $status = 'OK'
        if ($png.Length -le $FULL_FRAME_MAX) { $b64 = [Convert]::ToBase64String($png) }
        else { $status = 'PAYLOAD_TOO_LARGE' }
        Write-Reply @{ protocol_version = 'm2w.1'
            request_id = $Request.request_id
            worker_generation = $script:Generation
            configuration_revision = $script:Revision
            worker_mode = $script:Mode
            worker_status = 'OK'
            capture_status = $status
            window = $frame.window
            frame_content_status = (Get-ContentStatus -Bitmap $bitmap)
            effective_backend = $frame.backend_used
            backend_probe = $frame.probe_results
            no_backend_usable = [bool]$frame.no_backend_usable
            capture_ms = $frame.capture_ms
            frame_png_b64 = $b64 }
    } finally { $bitmap.Dispose() }
}

$setupCommands = @('REGION_SNAPSHOT', 'PREVIEW')
$initialized = $false

while ($null -ne ($line = [Console]::In.ReadLine())) {
    if ($line.Length -gt $REQUEST_LINE_MAX) { Write-Diag 'request line too long'; break }
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try { $request = ConvertFrom-Json -InputObject $line }
    catch { Write-Diag 'malformed request json'; break }
    $command = [string]$request.command
    if (-not $initialized) {
        if ($command -ne 'INIT') { Write-Diag 'first command must be INIT'; break }
        $initialized = Handle-Init $request
        if (-not $initialized) { break }
        continue
    }
    if (-not (Sync-Envelope $request $setupCommands)) { continue }
    switch ($command) {
        'HEALTH' {
            Write-Reply @{ protocol_version = 'm2w.1'
                request_id = $request.request_id
                worker_generation = $script:Generation
                configuration_revision = $script:Revision
                worker_mode = $script:Mode
                worker_status = 'OK' }
        }
        'REGION_SNAPSHOT' {
            $ui = [string]$request.ui_session_state
            if ($ui -ne 'TARGET_SELECTED' -and $ui -ne 'REGIONS_CONFIGURED') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'REGION_SNAPSHOT illegal in this state'
            } elseif ($script:Mode -eq 'RECORDING' -or $script:Mode -eq 'PAUSED') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'REGION_SNAPSHOT illegal while recording'
            } else { Handle-Snapshot $request ([bool]$request.probe_backend) }
        }
        'PREVIEW' {
            $ui = [string]$request.ui_session_state
            if ($ui -ne 'REGIONS_CONFIGURED' -or $script:Mode -eq 'RECORDING' -or
                $script:Mode -eq 'PAUSED' -or $script:Mode -eq 'ARMED') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'PREVIEW illegal in this state'
            } else {
                Handle-Capture $request $true
                $script:Mode = 'PREVIEWED'
                $script:PreviewedRevision = $script:Revision
            }
        }
        'ARM' {
            if ($script:Mode -ne 'PREVIEWED' -or
                $script:PreviewedRevision -ne $script:Revision) {
                Fail-Reply $request 'PROTOCOL_ERROR' 'ARM requires a fresh PREVIEW at this revision'
            } else {
                $script:Mode = 'ARMED'
                Write-Reply @{ protocol_version = 'm2w.1'
                    request_id = $request.request_id
                    worker_generation = $script:Generation
                    configuration_revision = $script:Revision
                    worker_mode = $script:Mode; worker_status = 'OK' }
            }
        }
        'DISARM' {
            if ($script:Mode -ne 'ARMED' -and $script:Mode -ne 'PAUSED') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'DISARM illegal in this mode'
            } else {
                $script:Mode = 'SETUP'; $script:PreviewedRevision = -1
                Write-Reply @{ protocol_version = 'm2w.1'
                    request_id = $request.request_id
                    worker_generation = $script:Generation
                    configuration_revision = $script:Revision
                    worker_mode = $script:Mode; worker_status = 'OK' }
            }
        }
        'RECORD_START' {
            if ($script:Mode -ne 'ARMED') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'RECORD_START requires ARMED'
            } else {
                $script:Mode = 'RECORDING'
                Write-Reply @{ protocol_version = 'm2w.1'
                    request_id = $request.request_id
                    worker_generation = $script:Generation
                    configuration_revision = $script:Revision
                    worker_mode = $script:Mode; worker_status = 'OK' }
            }
        }
        'CAPTURE' {
            if ($script:Mode -ne 'RECORDING') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'CAPTURE requires RECORDING'
            } else { Handle-Capture $request $false }
        }
        'PAUSE' {
            if ($script:Mode -ne 'RECORDING') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'PAUSE requires RECORDING'
            } else {
                $script:Mode = 'PAUSED'
                Write-Reply @{ protocol_version = 'm2w.1'
                    request_id = $request.request_id
                    worker_generation = $script:Generation
                    configuration_revision = $script:Revision
                    worker_mode = $script:Mode; worker_status = 'OK' }
            }
        }
        'RESUME' {
            if ($script:Mode -ne 'PAUSED') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'RESUME requires PAUSED'
            } else {
                $script:Mode = 'RECORDING'
                Write-Reply @{ protocol_version = 'm2w.1'
                    request_id = $request.request_id
                    worker_generation = $script:Generation
                    configuration_revision = $script:Revision
                    worker_mode = $script:Mode; worker_status = 'OK' }
            }
        }
        'STOP' {
            if ($script:Mode -ne 'RECORDING' -and $script:Mode -ne 'PAUSED') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'STOP requires RECORDING or PAUSED'
            } else {
                $script:Mode = 'STOPPED'
                Write-Reply @{ protocol_version = 'm2w.1'
                    request_id = $request.request_id
                    worker_generation = $script:Generation
                    configuration_revision = $script:Revision
                    worker_mode = $script:Mode; worker_status = 'OK' }
            }
        }
        'SHUTDOWN' {
            if ($script:Mode -eq 'RECORDING') {
                Fail-Reply $request 'PROTOCOL_ERROR' 'SHUTDOWN requires a non-recording mode (send STOP first)'
            } else {
                Write-Reply @{ protocol_version = 'm2w.1'
                    request_id = $request.request_id
                    worker_generation = $script:Generation
                    configuration_revision = $script:Revision
                    worker_mode = 'STOPPED'; worker_status = 'OK' }
                exit 0
            }
        }
        default { Fail-Reply $request 'PROTOCOL_ERROR' "unknown command $command" }
    }
}
Write-Diag 'stdin closed; worker exiting'
exit 0
