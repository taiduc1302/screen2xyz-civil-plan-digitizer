"""Deterministic synthetic single-coordinate DMS target (disposable
regression-test tool, stdlib-only - no Pillow/PIL, so it stays importable in
CI's windows-integration job which never installs third-party packages).

A minimal Tkinter window rendering one small (13pt) DMS coordinate string
("49°08'20.06\"N") at the same on-screen scale as a real map
application's lat/long readout (Google Earth owner test, 2026-07-19) - a
field scoped to just ONE coordinate, the way an owner would draw a region
around just the latitude portion of a combined readout line. Field height
is well under the 60px small-crop auto-upscale floor in
capture_worker_windows.ps1's Invoke-Ocr, so this exercises the real small
-text OCR path (upscale + padding fix, M2_IMPLEMENTATION_REPORT.md §5k)
feeding the new `coordinate` parse mode (Phase 1), end to end, against the
REAL worker + REAL Windows OCR engine - not a mock, and not a hand-picked
already-garbled string. Whatever the OCR engine actually produces for the
real ° glyph at this scale is what the parser has to cope with; the
test only pins the outcome CLASS (correct value or a specific safe-failure
status), never assumes a specific misread. Never displays real data.

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

VALUE = "49°08'20.06\"N"
CLIENT_W, CLIENT_H = 300, 80
# Same under-the-floor height as spike_small_text_target.py (28px < 60px),
# with generous (non-tight) horizontal margin around the longer DMS string.
FIELD_RECT = (10, 10, 260, 28)  # client x, y, w, h

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
    root.title(sys.argv[1] if len(sys.argv) > 1 else "S2XYZ-COORD-DMS")
    root.geometry(f"{CLIENT_W}x{CLIENT_H}+150+150")
    root.configure(bg="white")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    label = tk.Label(root, text=VALUE, font=("Segoe UI", 13), bg="white",
                     fg="black", anchor="w")
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
