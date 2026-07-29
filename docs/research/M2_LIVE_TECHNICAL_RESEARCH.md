# M2-Live Technical Research

## S7-SYNTHETIC result (G-E-SYNTHETIC, executed 2026-07-18)

Per OD-M2-9 the automated synthetic gate ran on the current machine using
`docs/research/spikes/spike_s7_synthetic_target.py` (deterministic Tk
target: known values `-123.654321`/`49.123456`/`87.05`, magenta marker,
controllable present/absent states, synthetic orange occluder) and
`spike_s7_synthetic_gate.py` (machine-readable oracles; no human input).
All **6/6 trial×backend combinations passed**:

| Trial | printwindow_clientonly | copyfromscreen |
|---|---|---|
| present | 900×300 @ DPI 96, marker ✓, OCR all values ✓ (22 ms) | same ✓ (31 ms) |
| absent | fields white ✓, OCR none ✓ (15 ms) | same ✓ (19 ms) |
| occluded | window content still readable ✓ (occlusion-immune on this GDI target) | occluder captured, values absent ✓ — documented visible-pixels semantics |

Cross-backend origin identical (128,151) in every trial; PNG size and
`frame_content_status` validated; target PID revalidated by the helper
before/after each capture. OCR matching is whitespace-normalized (Windows
OCR tokenizes `-123 . 654321`). Full machine report:
`.lab_work/m2_research/s7_synthetic_report.json` (ignored).

**Provisional backend (OD-M2-2 rule, synthetic-target evidence only):
`printwindow_clientonly`**, with `copyfromscreen` as the working fallback.
This closes **G-E-SYNTHETIC**. It is not a real-target claim: **G-E-REAL
remains pending** owner-machine validation, and occlusion immunity remains
target-specific.

Status: complete for M2-000 planning. All official claims cite the source
page; everything not verifiable from an official page or a local
measurement is listed as an ASSUMPTION or UNKNOWN. Access date for all
citations: 2026-07-17. Empirical spikes ran on the owner's machine
(Windows 11 Pro 10.0.26200, 2 monitors at 100% scaling, Windows PowerShell
5.1, Python 3.14.6, Tk 8.6); spike scripts are disposable and live only in
ignored `.lab_work/m2_research/`, except the sanitized owner-runnable S7
one-shot gate and its PW_CLIENTONLY/CopyFromScreen helper tracked under
`docs/research/spikes/`. Those two files are planning-gate tools, not
production M2 code. Raw logs and screenshots remain ignored and untracked.

Companion documents: [product spec](../requirements/M2_LIVE_PRODUCT_SPEC.md),
[architecture](../architecture/M2_LIVE_ARCHITECTURE.md),
[data contracts](../requirements/M2_LIVE_DATA_CONTRACTS.md).

## 1. Capture backends (official)

| # | Claim | Source | Limitation |
|---|---|---|---|
| C1 | `BitBlt` transfers pixels between DCs; `CAPTUREBLT` includes layered windows; Microsoft's own capture sample blits from a window DC obtained via `GetDC`. | [BitBlt function (wingdi.h)](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-bitblt) | Occluded/minimized/hw-accelerated/RDP behavior for window-DC capture is **undocumented**. |
| C2 | `GetDC(hWnd)` returns a client-area DC; `ReleaseDC` mandatory, same thread; DC single-threaded. | [GetDC function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getdc) | Occlusion semantics undocumented. |
| C3 | `Graphics.CopyFromScreen` (.NET 4.8.1, available to PowerShell 5.1) copies **visible screen pixels** at screen coordinates — not a window; throws `Win32Exception` on failure. | [Graphics.CopyFromScreen](https://learn.microsoft.com/en-us/dotnet/api/system.drawing.graphics.copyfromscreen?view=netframework-4.8.1) | Whatever overlaps the rect (occluders, tooltips) is captured; minimized/off-screen windows cannot be captured. |
| C4 | `PrintWindow` copies a visual window into a DC; the only documented flag is `PW_CLIENTONLY`; rendering happens via `WM_PRINT`/`WM_PRINTCLIENT` in the target app; the call is **blocking** and "might not return immediately" — must not run on a UI thread. | [PrintWindow function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow) | Output quality depends on the target's WM_PRINT handling; DirectX-rendered content may be blank; **no timeout exists**. `PW_RENDERFULLCONTENT` (0x2) appears on **no official page** — community-only, no compatibility contract → prohibited as a production dependency. |
| C5 | `Windows.Graphics.Capture` (Win10 1803+) captures windows/displays; Win32 interop via `IGraphicsCaptureItemInterop::CreateForWindow` (1903+); consent model draws a yellow border; frames arrive via a `Direct3D11CaptureFramePool` — **a D3D11 device is unavoidable**. `IsBorderRequired=false` requires `GraphicsCaptureAccess.RequestAccessAsync` consent. | [Screen capture](https://learn.microsoft.com/en-us/windows/uwp/audio-video-camera/screen-capture), [IGraphicsCaptureItemInterop](https://learn.microsoft.com/en-us/windows/win32/api/windows.graphics.capture.interop/nn-windows-graphics-capture-interop-igraphicscaptureiteminterop) | Out of reach for a stdlib-Python/PS-5.1 pipeline without substantial COM/D3D interop; occluded/minimized behavior not stated officially. Recorded as the **future backend seam**, not MVP. |
| C6 | DXGI Desktop Duplication is per-monitor only, D3D-only, max 4 concurrent duplications, `ProtectedContentMaskedOut` delivers DRM content pre-blacked. | [IDXGIOutput1::DuplicateOutput](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/nf-dxgi1_2-idxgioutput1-duplicateoutput), [DXGI_OUTDUPL_FRAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_2/ns-dxgi1_2-dxgi_outdupl_frame_info) | No per-window capture; rejected for MVP. |
| C7 | Apps can opt out of capture: `SetWindowDisplayAffinity` `WDA_MONITOR`/`WDA_EXCLUDEFROMCAPTURE` — such targets legitimately capture blank/absent under public capture APIs. | [SetWindowDisplayAffinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity) | Which capture APIs are affected is not enumerated per-API. |

## 2. DPI and coordinates (official)

| # | Claim | Source | Limitation |
|---|---|---|---|
| D1 | `SetProcessDpiAwarenessContext` must be called **before any HWND exists**; second attempts fail with `ERROR_ACCESS_DENIED`; default is UNAWARE. PMv2 = pseudo-handle −4. | [SetProcessDpiAwarenessContext](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setprocessdpiawarenesscontext), [DPI_AWARENESS_CONTEXT](https://learn.microsoft.com/en-us/windows/win32/hidpi/dpi-awareness-context) | Manifest is recommended; python.exe's manifest state is an UNKNOWN → the API path before importing/creating Tk UI is the practical option (S5 verified it works). |
| D2 | `GetDpiForWindow` returns DPI keyed on the **target hwnd's** awareness — an unaware target on a 150% monitor returns 96. | [GetDpiForWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getdpiforwindow) | Cross-process wording implied, not explicit. |
| D3 | Client capture rect recipe: origin = `ClientToScreen((0,0))`, size = `GetClientRect().right/bottom` (exclusive). `GetWindowRect` "is virtualized for DPI" and may include invisible resize borders → **not** used for capture rects. | [ClientToScreen](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-clienttoscreen), [GetWindowRect](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowrect) | Cross-awareness virtualization of client conversions is not per-API documented → mixed-DPI spike required on the owner's monitors when scaling ≠ 100%. |
| D4 | Virtual screen can have **negative coordinates**; SM_XVIRTUALSCREEN etc. | [The Virtual Screen](https://learn.microsoft.com/en-us/windows/win32/gdi/the-virtual-screen) | Confirmed locally: this machine's virtual screen starts at x=−1920. |
| D5 | `WM_DISPLAYCHANGE` is sent to top-level windows on resolution change — a hidden watcher window is a topology-change signal; re-query `MonitorFromWindow` rather than caching HMONITOR. | [WM_DISPLAYCHANGE](https://learn.microsoft.com/en-us/windows/win32/gdi/wm-displaychange), [MonitorFromWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-monitorfromwindow) | Whether it fires on scale-only changes is UNKNOWN → poll `GetDpiForWindow(target)` each tick as well. |
| D6 | A foreign window's `WM_DPICHANGED` cannot be observed → poll the target's DPI. | [WM_DPICHANGED](https://learn.microsoft.com/en-us/windows/win32/hidpi/wm-dpichanged) | — |
| D7 | Tk 8.6 `tk scaling` is points-per-pixel set at startup; official Tk/Python docs are **silent** on Windows DPI awareness. | [tk man page](https://www.tcl-lang.org/man/tcl8.6/TkCmd/tk.htm) | All Python/Tk DPI interplay is empirical (S5). |

## 3. Process, scheduling, cursor (official)

| # | Claim | Source | Limitation |
|---|---|---|---|
| P1 | `subprocess` docs warn of pipe-buffer deadlocks with bulk output; `communicate()` is one-shot — no blessed long-lived line protocol → keep messages small, drain stderr (validated by S2/S6 spikes). | [subprocess](https://docs.python.org/3/library/subprocess.html) | Long-lived protocol robustness is empirical. |
| P2 | `CREATE_NO_WINDOW` hides the child console (3.7+). | [subprocess](https://docs.python.org/3/library/subprocess.html) | Hidden-console Ctrl semantics undocumented. |
| P3 | `time.monotonic` cannot go backwards; QPC-backed on Windows in current CPython. | [time](https://docs.python.org/3/library/time.html) | No resolution guarantee stated. |
| P4 | Tk cross-thread calls are marshaled via the interpreter event queue but **fail if the event loop isn't running**; handlers must be fast; `after()` has no accuracy/drift guarantee → 1 Hz cadence needs monotonic deadline correction; worker I/O on a separate thread with queue+`after` handoff. | [tkinter](https://docs.python.org/3/library/tkinter.html), [Tcl after](https://www.tcl-lang.org/man/tcl8.6/TclCmd/after.htm) | Timer lateness unbounded under load — skipped ticks must be first-class. |
| P5 | Orphan prevention (belt and braces): Job object `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` kills children when the last job handle closes (kernel closes handles on parent death); child-side: `Process.GetProcessById(parentPid)` **once at startup** then `WaitForExit()` (avoids the documented PID-reuse race); stdin-close detection. | [JOBOBJECT_BASIC_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information), [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject), [Process.GetProcessById](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.getprocessbyid?view=netframework-4.8.1) | Create-then-assign job race is unclosed in stdlib (no `PROC_THREAD_ATTRIBUTE_JOB_LIST` in `subprocess`); stdin-close is the measured-working primary (S6), job object is hardening. |
| P6 | PS 5.1 `Add-Type` compiles C# to an in-memory assembly; types cannot be unloaded or changed within a session. | [Add-Type 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/add-type?view=powershell-5.1) | Per-session compile cost undocumented (S1/S2 measure total startup ≤ ~500 ms including it). |
| P7 | `GetCursorPos` returns screen coordinates (negative values legal on multi-monitor); `ScreenToClient` converts in place; RTL-layout windows need `MapWindowPoints`. | [GetCursorPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getcursorpos), [ScreenToClient](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-screentoclient) | DPI virtualization of cursor coords for non-aware processes undocumented — watcher is PMv2, so raw pixels. |
| P8 | For PS 5.1, only the encode direction (`$OutputEncoding`) is documented; the decode direction of native stdout via `[Console]::OutputEncoding` is **not** officially stated. | [about_Character_Encoding 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1) | Our protocol sets UTF-8 explicitly on both ends and is empirically clean (S2). |

## 4. OCR lifecycle (official)

| # | Claim | Source | Limitation |
|---|---|---|---|
| O1 | `OcrEngine.MaxImageDimension` is a static UInt32 with **no documented numeric value** — query at runtime. Measured on this machine: **10000**. | [MaxImageDimension](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine.maximagedimension) | Behavior for oversized input (exception vs silent) undocumented → validate before submit. |
| O2 | `TryCreateFromLanguage` returns **null** when the language can't resolve; `AvailableRecognizerLanguages` is the documented preflight; language packs installed via Windows Settings. | [TryCreateFromLanguage](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine.trycreatefromlanguage), [AvailableRecognizerLanguages](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine.availablerecognizerlanguages) | — |
| O3 | `OcrResult`/`OcrLine`/`OcrWord` expose Text, Lines/Words, `OcrWord.BoundingRect` (pixel space, valid at TextAngle 0), nullable `TextAngle` — and **no confidence property at any level**. | [OcrResult](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrresult), [OcrWord](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrword) | Confidence-based filtering is impossible by design → stability/status codes carry that role. |
| O4 | `SoftwareBitmap.CreateCopyFromBuffer(IBuffer, format, w, h[, alpha])` is the documented raw-bytes path (no stride param → tightly packed rows); `BitmapPixelFormat.Bgra8`=87, `BitmapAlphaMode.Ignore`=2 treats data as opaque. | [CreateCopyFromBuffer](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.imaging.softwarebitmap.createcopyfrombuffer), [BitmapPixelFormat](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.imaging.bitmappixelformat) | Which formats `RecognizeAsync` accepts is undocumented (sample code uses Bgra8); MVP may keep the PNG-stream decode path already proven in the baseline. |
| O5 | `IAsyncInfo.Cancel` has no promptness guarantee; async naming does **not** promise background-thread execution → never drive OCR from the UI thread; bound it with a worker-process timeout. | [IAsyncInfo](https://learn.microsoft.com/en-us/uwp/api/windows.foundation.iasyncinfo), [Async programming (UWP)](https://learn.microsoft.com/en-us/windows/uwp/threading-async/asynchronous-programming-universal-windows-platform-apps) | In-flight OCR may not actually stop — the worker process is the kill boundary. |
| O6 | **Support boundary:** the namespace page states Windows.Media.Ocr APIs "are only supported for desktop apps with package identity" (MSIX). | [Windows.Media.Ocr namespace](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr) | Policy, not enforcement — it works unpackaged (entire sealed baseline evidence proves it on this machine) but is outside the documented support envelope. Recorded in the risk register (RSK-M2-09). |
| O7 | OcrEngine/OcrResult/etc. carry ThreadingModel(Both)/Agile metadata → usable across threads. | [OcrEngine](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine) | Metadata-derived; no prose threading discussion. |

## 5. Empirical spike results (this machine, 2026-07-17)

All spikes use synthetic content. S1-S6 scripts and raw logs remain in ignored
`.lab_work/m2_research/` (`s1…s6_results.txt`). The sanitized S7 driver and its
one-capture helper are the two tracked disposable planning-gate tools under
`docs/research/spikes/`; their raw PNGs never enter Git.

| Spike | Measurement | Result |
|---|---|---|
| S1 — cold adapter cost | 5 runs of baseline `ocr_windows.ps1` end-to-end (spawn+WinRT+OCR+exit) | 442–525 ms per run (mean ≈ 471 ms) |
| S2 — long-lived worker | startup to READY; 60 sequential decode+OCR requests over stdin/stdout on a 1600×260 PNG | READY in **280 ms**; round-trip mean **17.3 ms** (p95 20.5, max 119 first-request JIT); OCR alone mean 5.1 ms; `MaxImageDimension`=10000; .NET GC heap did not grow |
| S3 — backend correctness (Tk/GDI target, 640×220 client) | capture + OCR of full client area, clear vs partially occluded by a topmost window | `copyfromscreen`: correct when clear; **captures the occluder** when occluded. `printwindow` flag 1 (PW_CLIENTONLY): clean client area, exact OCR, **identical result when occluded**, 14–15 ms. Flags 0 and 2 include title bar (geometry offset). |
| S4 — full synchronized tick | 30 ticks: one PrintWindow(PW_CLIENTONLY) frame → 3 in-memory crops → 3 OCRs, engine loaded once | capture mean **3.7 ms**; 3×OCR mean **13.9 ms**; total tick mean **23.6 ms**, p95 25 ms, max 140 ms; working set stable (about 100→91 MiB); all crops produced text every tick |
| S5 — DPI | PMv2 via ctypes before Tk; coordinate round-trip | `SetProcessDpiAwarenessContext(PMv2)` succeeded; `GetDpiForWindow`=96 (this machine runs **100% scaling** — mixed-DPI behavior NOT testable here); Tk winfo coords == physical pixels at 100%; 2 monitors; virtual screen origin −1920 (negative coords real) |
| S6 — orphan prevention | parent `os._exit(1)` without cleanup | worker exited within **1 s** via stdin-close detection |
| S7 — target-app gate | Tracked disposable tools: `docs/research/spikes/spike_s7_target_gate.py` + `spike_s3_capture.ps1`. Each invocation binds HWND+PID, rejects hidden/minimized or mid-capture identity/DPI/geometry changes, labels one trial (`present`, `absent`, or `occluded`), shows a 3–5 s countdown, then performs one bounded capture with PW_CLIENTONLY and one with CopyFromScreen—no continuous loop. Successful cross-backend results must have equal dimensions/origin/DPI. An in-process 1:1 scrollable local viewer collects a factual verdict for each validated preview. Results distinguish capture-API failure from trial-invalid timeout/protocol/state/infrastructure failure; exit zero requires no invalid outcome, at least one validated preview, and explicit verdicts for every validated preview, but does not pass G-E. Default transient PNGs are deleted on normal completion. Forced termination can leave sensitive non-evidence/partial files in the OS temp directory or an incomplete ignored save directory; a directory without the final record is not complete evidence. Explicit `--save` uses a unique ignored directory under `.lab_work/m2_research/s7_preview/` and publishes a no-overwrite sanitized `trial_record.json` last, after a SHA-256 manifest binds each validated PNG to its trial/backend/verdict. Required procedure is three separate invocations, one per trial; occluded covers the identified value area with a benign non-confidential occluder. | **Authored as a planning gate; not executed against the intended target.** OD-M2-8/G-F permission and authorized demonstration content are prerequisites. S7 records target/environment-specific support only. |

Environment limits of these measurements: single machine, 100% scaling on
both monitors, GDI-rendered (Tk) target only, no RDP/HDR/protected content,
harness sandbox filtered cross-process window *enumeration* (direct HWND
access worked; enumeration/pickers must be re-verified in S7 on a normal
desktop session).

## 6. Assumptions and unknowns (owner-machine or implementation-time)

1. **UNKNOWN (S7 after OD-M2-8/G-F):** whether the intended target application is GDI-printable
   (PrintWindow works) or hardware-accelerated (CopyFromScreen-only, must
   stay visible) or capture-protected (blank under both). Gate M2-001.
2. **UNKNOWN:** mixed-DPI (125/150%) coordinate virtualization for
   cross-process client rects — untestable at 100% scaling; re-run S5 when
   any monitor scaling ≠ 100%.
3. **UNKNOWN:** whether WM_DISPLAYCHANGE fires on scale-only changes →
   design polls target DPI per tick regardless.
4. **ASSUMPTION (empirically supported, officially unstated):**
   Windows.Media.Ocr works from unpackaged processes (proven by the sealed
   baseline evidence on this machine); documented support requires package
   identity (O6).
5. **ASSUMPTION:** 1 msg/s line-framed pipe protocol cannot deadlock given
   small messages and drained stderr (S2 ran 60 requests cleanly; soak test
   in M2-009/M2-010 will exercise 1800+).
6. **UNKNOWN:** minimum text pixel height for reliable OCR — no official
   number; the preview gate plus optional crop upscaling (factor 1–4, GDI
   interpolation, bounded by MaxImageDimension) is the mitigation.
7. **UNKNOWN:** PrintWindow behavior for a minimized target (undocumented)
   — MVP checks `IsIconic` before capture and reports
   `capture_status=TARGET_MINIMIZED`, never trusting whatever PrintWindow
   returns for it.

## 7. Performance and resource budget

Numeric product limits below mirror the authoritative data-contract §0
table; measured rows remain explicitly machine/spike-specific.

| Quantity | Value | Basis |
|---|---|---|
| Default interval | 1000 ms | owner requirement (measured headroom ×40) |
| Max supported sources (MVP) | 8 | target: 8×OCR ≈ 40 ms/tick from S4 per-crop ≈ 4.6 ms — target, not measured at 8 |
| Capture duration target | ≤ 50 ms | measured 3.7 ms mean (S4 — **640×220 GDI client via PrintWindow**; large clients and CopyFromScreen unmeasured → T-M2L-040) |
| Per-crop OCR target | ≤ 100 ms | measured ≈ 4.6 ms mean (S4, same geometry caveat; crop-hash cost unmeasured) |
| Slow-tick soft alarm | tick > interval − 100 ms | advisory diagnostics threshold only — the scheduler's actual skip rule is the single-outstanding-request invariant with an interval×2 (min 2 s) timeout (architecture §6) |
| Worker startup | ≤ 3 s budget | measured 280 ms (S2) |
| Memory growth over 30 min | ≤ 50 MiB budget | measured: none over 30 ticks (S4) — 30-min soak is an M2-010 owner-machine test |
| Max crop size | 2000×800 px | assumption pending real-target fields; enforced by region validation |
| Bounding-frame cap | target window client area ≤ 8192×8192 | aligns with M1 intake caps |
| Candidate evidence / protocol | PNG ≤8 MiB/source and ≤64 MiB aggregate; canonical metadata ≤16 KiB/source and ≤128 KiB aggregate; accounted owned bytes ≤8 MiB+16 KiB/source and ≤64 MiB+128 KiB aggregate; setup frame ≤64 MiB; JSON line ≤96 MiB | bounded planning limits; future T-M2L-009/020/024/026 |
| Session disk warning / default cap | 200 MiB warn / 500 MiB stop | assumption — owner decision OD-M2-3 |
| Max session duration (MVP) | 4 h | **advisory only — not enforced anywhere in MVP**; journal has no inherent limit |
| Max retained events per session | 50 000 | **advisory only — not enforced**; ~1.5 KB/event + crops; the enforced limits are the disk caps (M2-FR-063) |

Measured values are from S1–S6 above; "target/assumption" rows are labeled
and must be re-validated on the owner's machine in M2-009/M2-010.
