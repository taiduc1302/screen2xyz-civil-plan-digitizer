"""Deterministic synthetic one-line, three-value coordinate overlay target
(disposable regression-test tool, stdlib-only - no Pillow/PIL, so it stays
importable in CI's windows-integration job which never installs third-party
packages).

Phase 2 (2026-07-19): the real target's coordinate readout is not three
separate lines (the S7 fixture's convenient layout) - it is ONE thin
overlay line holding lat+long+elev together, e.g.
"49°08'20.06"N 123°03'41.61"W 87.05", at realistic small on-screen scale
(13pt, ~24px tall - see spike_small_text_target.py). This target renders
exactly that line, measured (see M2_IMPLEMENTATION_REPORT.md §5k Phase 2.1)
at 13pt Segoe UI to have only ~5px of gap between adjacent values - too
narrow a margin for a human to reliably draw three separate, non-touching
sub-regions by mouse, and narrower than the 12px minimum margin Phase 0
itself found OCR needs to reliably recognize text at all. Used both to
reproduce that difficulty against the real pipeline (three tight,
pixel-computed sub-regions, best-case zero extra slack) and to prove the
Phase 2 fix (one shared region + `line_part`) against the real controller +
real worker + real OCR engine. Never displays real data.

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
import tkinter.font as tkfont

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

VALUE = "49°08'20.06\"N 123°03'41.61\"W 87.05"
TOKENS = VALUE.split(" ")
CLIENT_W, CLIENT_H = 300, 44
FIELD_ORIGIN = (10, 10)  # client x, y where the line is drawn
FIELD_H = 24  # under the 60px small-crop floor, matching the real bug scale

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
    root.title(sys.argv[1] if len(sys.argv) > 1 else "S2XYZ-COORD-LINE")
    root.geometry(f"{CLIENT_W}x{CLIENT_H}+150+150")
    root.configure(bg="white")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    font = tkfont.Font(family="Segoe UI", size=13)
    label = tk.Label(root, text=VALUE, font=font, bg="white", fg="black",
                     anchor="w")
    label.place(x=FIELD_ORIGIN[0], y=FIELD_ORIGIN[1],
               width=280, height=FIELD_H)

    # Exact per-token pixel spans within the rendered line, measured the
    # same way as the Phase 2.1 evidence script - lets a test compute the
    # tightest-possible (best-case, zero extra slack) 3-way sub-region
    # split, and the ONE whole-line region the line_part fix uses instead.
    spans = []
    pos = 0
    for tok in TOKENS:
        idx = VALUE.index(tok, pos)
        prefix = VALUE[:idx]
        start_px = font.measure(prefix)
        end_px = start_px + font.measure(tok)
        spans.append([start_px, end_px])
        pos = idx + len(tok)

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
        "field_origin": list(FIELD_ORIGIN),
        "field_h": FIELD_H,
        "value": VALUE,
        "tokens": TOKENS,
        "token_spans_px": spans,
    }
    print(json.dumps(ready), flush=True)
    threading.Thread(target=stdin_reader, daemon=True).start()
    root.after(50, pump)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
