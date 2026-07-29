"""Deterministic synthetic S7 target (disposable planning-gate tool).

A non-confidential Tkinter window with known numeric fields, a magenta
pixel marker, controllable present/absent field states, and a benign
synthetic occluder. Controlled over stdin with JSON lines; reports its own
root HWND, PID, client size, and DPI on startup so the harness never needs
title-based lookup. Never displays real data.

Commands (one JSON object per line on stdin):
  {"cmd": "present"}        -> show the three known values
  {"cmd": "absent"}         -> blank all three fields
  {"cmd": "occlude"}        -> topmost orange occluder over the field area
  {"cmd": "clear_occlude"}  -> remove the occluder
  {"cmd": "quit"}           -> exit
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

VALUES = ("-123.654321", "49.123456", "87.05")
CLIENT_W, CLIENT_H = 900, 300
FIELD_X, FIELD_YS = 30, (40, 120, 200)
MARKER_RECT = (840, 10, 50, 50)          # client x, y, w, h
OCCLUDER_RECT = (20, 20, 500, 240)       # covers fields, not the marker

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
    root.title(sys.argv[1] if len(sys.argv) > 1 else "S2XYZ-SYN-TARGET")
    root.geometry(f"{CLIENT_W}x{CLIENT_H}+120+120")
    root.configure(bg="white")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    labels = []
    for y in FIELD_YS:
        label = tk.Label(root, text="", font=("Consolas", 22), bg="white", fg="black", anchor="w")
        label.place(x=FIELD_X, y=y, width=470, height=44)
        labels.append(label)
    marker = tk.Frame(root, bg="#ff00ff")
    marker.place(x=MARKER_RECT[0], y=MARKER_RECT[1], width=MARKER_RECT[2], height=MARKER_RECT[3])

    occluder: dict[str, tk.Toplevel | None] = {"window": None}

    def set_state(mode: str) -> None:
        for label, value in zip(labels, VALUES):
            label.configure(text=value if mode == "present" else "")

    def set_occluder(show: bool) -> None:
        if show and occluder["window"] is None:
            top = tk.Toplevel(root)
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            x = root.winfo_rootx() + OCCLUDER_RECT[0]
            y = root.winfo_rooty() + OCCLUDER_RECT[1]
            top.geometry(f"{OCCLUDER_RECT[2]}x{OCCLUDER_RECT[3]}+{x}+{y}")
            frame = tk.Frame(top, bg="#ff8800")
            frame.pack(fill="both", expand=True)
            tk.Label(frame, text="SYNTHETIC OCCLUDER", font=("Arial", 18), bg="#ff8800").place(
                relx=0.5, rely=0.5, anchor="center"
            )
            occluder["window"] = top
        elif not show and occluder["window"] is not None:
            occluder["window"].destroy()
            occluder["window"] = None

    def pump() -> None:
        try:
            while True:
                command = commands.get_nowait()
                name = command.get("cmd", "")
                if name == "quit":
                    print(json.dumps({"ok": "quit"}), flush=True)
                    root.destroy()
                    return
                if name in ("present", "absent"):
                    set_state(name)
                elif name == "occlude":
                    set_occluder(True)
                elif name == "clear_occlude":
                    set_occluder(False)
                root.update_idletasks()
                print(json.dumps({"ok": name}), flush=True)
        except queue.Empty:
            pass
        root.after(50, pump)

    set_state("present")
    root.update()
    hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)
    ready = {
        "ready": True,
        "pid": ctypes.windll.kernel32.GetCurrentProcessId(),
        "hwnd": int(hwnd),
        "client_w": root.winfo_width(),
        "client_h": root.winfo_height(),
        "dpi": int(ctypes.windll.user32.GetDpiForWindow(hwnd)),
        "marker_center": [MARKER_RECT[0] + MARKER_RECT[2] // 2, MARKER_RECT[1] + MARKER_RECT[3] // 2],
        "field_center": [OCCLUDER_RECT[0] + OCCLUDER_RECT[2] // 2, OCCLUDER_RECT[1] + OCCLUDER_RECT[3] // 2],
        "values": list(VALUES),
    }
    print(json.dumps(ready), flush=True)
    threading.Thread(target=stdin_reader, daemon=True).start()
    root.after(50, pump)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
