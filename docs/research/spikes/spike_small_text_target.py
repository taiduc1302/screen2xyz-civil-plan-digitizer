"""Deterministic synthetic small-text target (disposable regression-test
tool, stdlib-only - no Pillow/PIL, so it stays importable in CI's
windows-integration job which never installs third-party packages).

A minimal Tkinter window rendering one small (13pt) numeric label at the
same on-screen scale as real small UI text - status bars, HUD overlays,
coordinate readouts. A real owner test (Google Earth's lat/long/elevation
readout, 2026-07-19) found Windows.Media.Ocr returned no text at all for
this scale at a field's default upscale (1) - root-caused and fixed in
capture_worker_windows.ps1's Invoke-Ocr (a crop shorter than 60px is now
upscaled at least 3x for OCR internally, regardless of the field's own
setting). This target lets a regression test exercise that fix against the
REAL worker + REAL Windows OCR engine, not a mock. Never displays real
data.

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

VALUE = "42.5"
CLIENT_W, CLIENT_H = 300, 80
# Deliberately at the real-world bug's scale: a 13pt label in a ~28px-tall
# field, well under the 60px floor in Invoke-Ocr's small-crop auto-upscale.
FIELD_RECT = (10, 10, 200, 28)  # client x, y, w, h

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
    root.title(sys.argv[1] if len(sys.argv) > 1 else "S2XYZ-SMALL-TEXT")
    root.geometry(f"{CLIENT_W}x{CLIENT_H}+140+140")
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
