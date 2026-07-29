"""Deterministic synthetic tight-margin text target (disposable
regression-test tool, stdlib-only - no Pillow, so it stays importable in
CI's windows-integration job which never installs third-party packages).

Phase 0 boundary audit (2026-07-19) finding: a controlled sweep of directly
-constructed synthetic PNG crops, fed to the real shipped Invoke-Ocr
function, proved the small-crop auto-upscale floor alone does NOT fix a
near-zero-margin region - exactly what the app's own troubleshooting text
recommended ("redraw the region tighter around just the digits"): margin
around the ink turned out to be at least as load-bearing as scale for
those PNG crops. This target renders text with the Tk label's own
internal padding stripped to zero (padx=0, pady=0, borderwidth=0,
highlightthickness=0), sized just large enough to contain the full glyph
cell without clipping it, to test that same near-zero-margin condition
against a REAL captured window rather than a synthetic PNG. Real Windows-
rendered (ClearType) text turned out to be more OCR-forgiving at tight
margins than the PIL-rendered PNG crops at equivalent nominal dimensions -
see TightMarginOcrRegressionTests' docstring for the honest account of
what this specific pathway does and does not prove.

Controlled over stdin with one JSON command per line:
  {"cmd": "quit"}  -> exit
Each applied command is acknowledged with {"ok": "<cmd>"} on stdout.
"""

from __future__ import annotations

import ctypes
import json
import queue
import sys
import threading
import tkinter as tk

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

VALUE = "42.567"
# Segoe UI 14pt measures: width("42.567")=54px, linespace=25px (ascent 20 +
# descent 5). Sized to just contain the full glyph cell (no clipping) with
# only 1-2px of slack - the minimal-but-not-clipping margin a real user
# would get from carefully, tightly redrawing a region around the digits.
CLIENT_W, CLIENT_H = 58, 26
# Deliberately near-zero margin: the label fills nearly the whole client
# area, with Tk's own internal padding stripped to zero, so the captured
# region has only a few pixels of breathing room around the ink on every
# side - the exact condition the boundary audit found broke OCR at every
# upscale factor with no padding step.
FIELD_RECT = (0, 0, CLIENT_W, CLIENT_H)

commands: "queue.Queue[dict]" = queue.Queue()


def stdin_reader() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            commands.put(json.loads(line))
        except json.JSONDecodeError:
            commands.put({"cmd": "quit"})
            return


def main() -> int:
    root = tk.Tk()
    root.title(sys.argv[1] if len(sys.argv) > 1 else "S2XYZ-TIGHT-MARGIN")
    root.geometry(f"{CLIENT_W}x{CLIENT_H}+160+160")
    root.configure(bg="white")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    label = tk.Label(root, text=VALUE, font=("Segoe UI", 14), bg="white",
                     fg="black", anchor="nw", padx=0, pady=0,
                     borderwidth=0, highlightthickness=0)
    label.place(x=FIELD_RECT[0], y=FIELD_RECT[1], width=FIELD_RECT[2],
               height=FIELD_RECT[3])

    def pump() -> None:
        try:
            while True:
                command = commands.get_nowait()
                name = command.get("cmd", "")
                if name == "quit":
                    print(json.dumps({"ok": "quit"}), flush=True)
                    root.destroy()
                    return
                root.update_idletasks()
                print(json.dumps({"ok": name}), flush=True)
        except queue.Empty:
            pass
        root.after(50, pump)

    root.update()
    hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)
    ready = {
        "ready": True,
        "pid": ctypes.windll.kernel32.GetCurrentProcessId(),
        "hwnd": int(hwnd),
        "client_w": root.winfo_width(),
        "client_h": root.winfo_height(),
        "dpi": int(ctypes.windll.user32.GetDpiForWindow(hwnd)),
        "field_rect": list(FIELD_RECT),
        "value": VALUE,
    }
    print(json.dumps(ready), flush=True)
    threading.Thread(target=stdin_reader, daemon=True).start()
    root.after(50, pump)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
