"""Minimal, dependency-free (stdlib Tk only) local image fixture window
(§13's "controlled local image fixture window" alternative to driving
Windows Photos/Paint, which needs computer-use). Displays one PNG at 1:1,
reports its own hwnd/pid/client size as one JSON line on stdout so the
scenario runner never needs title-based lookup, then waits for "quit" on
stdin. Never displays anything but the given synthetic fixture file."""

from __future__ import annotations

import json
import sys
import threading
import tkinter as tk


def main() -> None:
    path = sys.argv[1]
    root = tk.Tk()
    root.title("Screen2XYZ image fixture viewer")
    image = tk.PhotoImage(file=path)
    label = tk.Label(root, image=image, borderwidth=0)
    label.pack()
    root.update_idletasks()
    hwnd = root.winfo_id()
    import os
    ready = {"hwnd": hwnd, "pid": os.getpid(),
            "client_w": image.width(), "client_h": image.height()}
    print(json.dumps(ready), flush=True)

    def read_stdin() -> None:
        for line in sys.stdin:
            if line.strip() == "quit":
                root.after(0, root.destroy)
                return

    threading.Thread(target=read_stdin, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
