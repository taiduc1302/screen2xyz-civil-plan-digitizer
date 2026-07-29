"""Screen2XYZ M2-Live synthetic demo target (Windows, Tk).

A non-confidential, deterministic window with labeled X/Y/Z number fields
that Screen2XYZ can watch end to end. Used by both the interactive `demo`
launch (a window a new owner can freely experiment against, with zero risk
of touching real data) and the automated self-test (which drives it through
scripted cases over stdin). Never displays real data.

Reports its own root HWND, PID, client size, DPI, the exact field rects, a
protocol version, and a per-process session token on startup as one JSON
line, so the caller never needs title-based lookup or manual region drawing
to get started, and every subsequent exchange can be verified rather than
assumed (§6: a deterministic protocol, not timing-based readiness).

Commands (one JSON object per line on stdin), each carrying the caller's
`seq` (int) and `session_token` (echoed back verbatim so a late/duplicate
ack from an earlier command can never be mistaken for the current one) and
acknowledged with {"ok": <bool-or-cmd-name>, "seq":..., "session_token":...,
"protocol_version":...} on stdout:
  {"cmd": "case", "name": "stable"|"changing"|"empty"|"malformed"|
                          "unicode_minus"}
  {"cmd": "auto_change", "on": true|false}   -- periodic nudge while
                                                 case == "changing"
  {"cmd": "resize", "w": <int>, "h": <int>}
  {"cmd": "maximize"} / {"cmd": "restore"} / {"cmd": "minimize"}
  {"cmd": "occlude"} / {"cmd": "clear_occlude"}
  {"cmd": "quit"}
An unrecognized `cmd` is acknowledged honestly with {"ok": false,
"error": "UNKNOWN_COMMAND"} rather than a false {"ok": "<cmd>"}.
"""

from __future__ import annotations

import ctypes
import json
import queue
import random
import secrets
import sys
import threading
import tkinter as tk

from screen2xyz_m2.contracts import DEMO_PROTOCOL_VERSION as PROTOCOL_VERSION

KNOWN_COMMANDS = frozenset({
    "case", "auto_change", "resize", "maximize", "restore", "minimize",
    "occlude", "clear_occlude", "quit",
})

# The command pump is re-scheduled at this interval (§9). It was 50 ms, which
# instrumentation showed was the DOMINANT handshake latency (a command sat in
# the queue up to ~50 ms - and longer whenever the Tk loop was momentarily
# busy - before the poll picked it up; the actual apply+ack is ~1.5 ms). A
# tighter 10 ms poll cuts that pickup latency ~5x and shrinks the window in
# which a transient Tk-loop stall can push an ack past the client timeout, so
# the primary path no longer needs a retry. (Tk on Windows cannot register a
# pipe file-handler in its event loop, so a short poll is the pragmatic
# event-loop-safe mechanism; the cost of an empty poll is negligible.)
PUMP_INTERVAL_MS = 10

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

CLIENT_W, CLIENT_H = 900, 320
FIELD_X = 30
# Geometry and font match the S7 synthetic target (docs/research/spikes/
# spike_s7_synthetic_target.py), proven reliable across this project's real
# OCR integration tests - inventing new dimensions here previously produced
# OCR artifacts (phantom leading digits) that this known-good geometry does
# not exhibit.
FIELD_ROWS = (("X", 40), ("Y", 120), ("Z", 200))
FIELD_W, FIELD_H = 470, 44
# The caption ("field X"/"Y"/"Z") sits on its own line ABOVE the value, never
# beside it, so the reported field rect - which is exactly the value label's
# bounds - can never OCR the caption text concatenated with the number.
CAPTION_H = 18
STATUS_Y = 260
OCCLUDER_RECT = (20, 15, 520, 235)

BASE_VALUES = {"X": -123.654321, "Y": 49.123456, "Z": 87.05}

commands: "queue.Queue[dict]" = queue.Queue()

# Opt-in diagnostic timestamps (§9): when S2XYZ_DEMO_DIAG=1, the target
# writes one JSON line to STDERR per command with monotonic timestamps for
# stdin-enqueue, pump-dequeue, and ack-send, so the caller can localise any
# handshake latency (Tk pump starvation vs pipe scheduling). Off by default,
# so normal operation and the stdout protocol are completely unaffected.
import os as _os
import time as _time
_DIAG = _os.environ.get("S2XYZ_DEMO_DIAG") == "1"


def _diag(**fields: object) -> None:
    if _DIAG:
        try:
            sys.stderr.write(json.dumps(fields) + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def stdin_reader() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
            cmd["_enqueued_ms"] = _time.monotonic() * 1000
            commands.put(cmd)
        except json.JSONDecodeError:
            commands.put({"cmd": "quit"})
            return


def main() -> int:
    root = tk.Tk()
    root.title(sys.argv[1] if len(sys.argv) > 1 else "S2XYZ-M2-DEMO-TARGET")
    root.geometry(f"{CLIENT_W}x{CLIENT_H}+120+120")
    root.configure(bg="white")
    root.attributes("-topmost", True)

    status_var = tk.StringVar(value="case: stable")
    tk.Label(root, textvariable=status_var, font=("Consolas", 12),
             bg="white", fg="#666666", anchor="w").place(
        x=FIELD_X, y=STATUS_Y, width=700, height=30)

    labels: dict[str, tk.Label] = {}
    for name, y in FIELD_ROWS:
        tk.Label(root, text=f"field {name}", font=("Consolas", 11),
                 bg="white", fg="#204060", anchor="w").place(
            x=FIELD_X, y=y - CAPTION_H, width=200, height=CAPTION_H)
        label = tk.Label(root, text="", font=("Consolas", 22), bg="white",
                          fg="black", anchor="w")
        label.place(x=FIELD_X, y=y, width=FIELD_W, height=FIELD_H)
        labels[name] = label

    state = {"case": "stable", "auto_change": False,
             "values": dict(BASE_VALUES)}
    occluder: dict[str, tk.Toplevel | None] = {"window": None}

    def render() -> None:
        case = state["case"]
        status_var.set(f"case: {case}  auto_change: {state['auto_change']}")
        if case == "empty":
            for label in labels.values():
                label.configure(text="")
            return
        if case == "malformed":
            for name, label in labels.items():
                label.configure(text="N/A#error")
            return
        for name, label in labels.items():
            value = state["values"][name]
            if case == "unicode_minus" and value < 0:
                # U+2212 MINUS SIGN, not ASCII hyphen - exercises the closed
                # Unicode sign-normalization policy in parsing.py.
                text = "−" + f"{abs(value):.6f}"
            else:
                text = f"{value:.6f}"
            label.configure(text=text)

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
            tk.Label(frame, text="SYNTHETIC OCCLUDER", font=("Arial", 18),
                      bg="#ff8800").place(relx=0.5, rely=0.5, anchor="center")
            occluder["window"] = top
        elif not show and occluder["window"] is not None:
            occluder["window"].destroy()
            occluder["window"] = None

    def apply(command: dict) -> str | None:
        """Returns the applied command name, or None for an unrecognized
        command - the caller turns that into an honest {"ok": false} ack
        instead of pretending an unknown command succeeded."""

        name = command.get("cmd", "")
        if name not in KNOWN_COMMANDS:
            return None
        if name == "case":
            case_name = command.get("name", "stable")
            state["case"] = case_name
            if case_name != "changing":
                state["values"] = dict(BASE_VALUES)
            render()
        elif name == "auto_change":
            state["auto_change"] = bool(command.get("on", False))
        elif name == "resize":
            w = int(command.get("w", CLIENT_W))
            h = int(command.get("h", CLIENT_H))
            root.geometry(f"{w}x{h}")
        elif name == "maximize":
            root.state("zoomed")
        elif name == "restore":
            root.state("normal")
            root.geometry(f"{CLIENT_W}x{CLIENT_H}+120+120")
        elif name == "minimize":
            root.iconify()
        elif name == "occlude":
            set_occluder(True)
        elif name == "clear_occlude":
            set_occluder(False)
        return name

    def ack(command: dict, ok) -> dict:
        reply: dict = {"ok": ok, "protocol_version": PROTOCOL_VERSION}
        if "seq" in command:
            reply["seq"] = command["seq"]
        if "session_token" in command:
            reply["session_token"] = command["session_token"]
        if ok is False:
            reply["error"] = "UNKNOWN_COMMAND"
            reply["cmd"] = command.get("cmd", "")
        return reply

    def pump_commands() -> None:
        try:
            while True:
                command = commands.get_nowait()
                dequeued = _time.monotonic() * 1000
                name = command.get("cmd", "")
                if name == "quit":
                    print(json.dumps(ack(command, "quit")), flush=True)
                    root.destroy()
                    return
                applied = apply(command)
                root.update_idletasks()
                print(json.dumps(ack(command, applied if applied is not None
                                     else False)), flush=True)
                enq = command.get("_enqueued_ms")
                _diag(cmd=name, seq=command.get("seq"),
                      enqueue_to_dequeue_ms=(dequeued - enq
                                            if enq is not None else None),
                      dequeue_to_ack_ms=_time.monotonic() * 1000 - dequeued)
        except queue.Empty:
            pass
        root.after(PUMP_INTERVAL_MS, pump_commands)

    def auto_change_tick() -> None:
        if state["auto_change"] and state["case"] == "changing":
            for name in state["values"]:
                state["values"][name] += random.uniform(-0.5, 0.5)
            render()
        root.after(300, auto_change_tick)

    render()
    root.update()
    hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)
    ready = {
        "ready": True,
        "protocol_version": PROTOCOL_VERSION,
        "session_token": secrets.token_hex(8),
        "pid": ctypes.windll.kernel32.GetCurrentProcessId(),
        "hwnd": int(hwnd),
        "client_w": root.winfo_width(),
        "client_h": root.winfo_height(),
        "dpi": int(ctypes.windll.user32.GetDpiForWindow(hwnd)),
        "fields": {name: [FIELD_X, y, FIELD_W, FIELD_H]
                   for name, y in FIELD_ROWS},
    }
    # Start the stdin reader and schedule the command pump BEFORE printing
    # "ready" - the caller is free to write its first command the instant it
    # sees this line, so the reader thread must already be alive and blocked
    # on stdin, never started as a race against the client's first write.
    threading.Thread(target=stdin_reader, daemon=True).start()
    root.after(PUMP_INTERVAL_MS, pump_commands)
    root.after(300, auto_change_tick)
    print(json.dumps(ready), flush=True)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
