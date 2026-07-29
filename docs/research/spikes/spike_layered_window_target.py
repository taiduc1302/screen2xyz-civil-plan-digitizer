"""Disposable target: a layered (DWM-composited) Tk window.

A `-alpha` value just under fully opaque forces Windows to treat the window
as layered/composited. This is a known trigger for legacy PrintWindow(0) to
either return blank/uniform content or hang outright, while the window
renders correctly on screen (CopyFromScreen sees it fine). Used only to
validate the M2 worker's Auto-backend fallback and its bounded PrintWindow
timeout (adapters/capture_worker_windows.ps1) against a real, reproducible
instance of that failure mode. Never displays real data.
"""

from __future__ import annotations

import ctypes
import json
import sys
import tkinter as tk

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

CLIENT_W, CLIENT_H = 500, 300

root = tk.Tk()
root.title(sys.argv[1] if len(sys.argv) > 1 else "S2XYZ-LAYERED-TARGET")
root.geometry(f"{CLIENT_W}x{CLIENT_H}+150+150")
root.configure(bg="#204060")
root.attributes("-alpha", 0.999)
root.attributes("-topmost", True)
label = tk.Label(root, text="123.456", font=("Consolas", 28), bg="#204060",
                 fg="white")
label.place(x=30, y=30, width=400, height=60)
root.update()
hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)
print(json.dumps({"ready": True,
                  "pid": ctypes.windll.kernel32.GetCurrentProcessId(),
                  "hwnd": int(hwnd), "client_w": root.winfo_width(),
                  "client_h": root.winfo_height()}), flush=True)
sys.stdin.readline()  # block until the parent writes anything, then exit
root.destroy()
