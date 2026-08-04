"""Always-on-top live capture status window."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ..capture import CapturedPoint
from ..operations import ZoneHealthSnapshot, zone_indicator_states


class CaptureOverlay(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_pause: Callable[[], None],
        on_stop: Callable[[], None],
        on_repick: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("Screen2XYZ capture")
        self.attributes("-topmost", True)
        self.geometry("900x210")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", on_stop)
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        self._summary = tk.StringVar(value="No rows captured yet")
        self._health = tk.StringVar(value="Waiting for zone readings")
        self._zones = tk.StringVar(value="X: —   Y: —   Z: —")
        ttk.Label(body, text="Live capture", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(body, textvariable=self._summary).pack(anchor="w", pady=(4, 0))
        self.health_label = tk.Label(
            body,
            textvariable=self._health,
            fg="#9a3412",
            justify="left",
            wraplength=860,
        )
        self.health_label.pack(anchor="w", pady=(4, 0))
        zone_row = ttk.Frame(body)
        zone_row.pack(fill="x", pady=(2, 8))
        self._zone_labels: dict[str, tk.Label] = {}
        for name in ("x", "y", "z"):
            label = tk.Label(zone_row, text=f"{name.upper()}: —", fg="#b91c1c")
            label.pack(side="left", padx=(0, 12))
            self._zone_labels[name] = label
        actions = ttk.Frame(body)
        actions.pack(fill="x")
        self.pause_button = ttk.Button(actions, text="Pause / resume", command=on_pause)
        self.pause_button.pack(side="left")
        self.repick_button = ttk.Button(actions, text="Re-pick zones", command=on_repick)
        self.repick_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(actions, text="Stop", command=on_stop)
        self.stop_button.pack(side="right")

    def show_point(self, point: CapturedPoint, count: int) -> None:
        z_text = "MISSING (PARTIAL)" if point.z is None else f"{point.z:g}"
        self._summary.set(
            f"{count} rows · last: {point.x:g}, {point.y:g}, {z_text}"
        )

    def show_health(self, snapshot: ZoneHealthSnapshot) -> None:
        self._health.set(snapshot.message)
        self.health_label.configure(fg="#15803d" if snapshot.ok else "#b91c1c")
        for name, (value, ok) in zone_indicator_states(snapshot).items():
            label = self._zone_labels[name]
            label.configure(
                text=f"{name.upper()}: {value}",
                fg="#15803d" if ok else "#b91c1c",
            )
