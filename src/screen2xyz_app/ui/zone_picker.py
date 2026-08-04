"""Fullscreen rectangle picker with OCR preview callback."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from ..operations import (
    current_virtual_desktop_bounds,
    format_virtual_geometry,
    preview_without_overlay,
    screen_zone_from_drag,
    zone_preview_assessment,
)

Zone = tuple[int, int, int, int]


class ZonePicker(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        preview: Callable[[Zone], str],
        on_accept: Callable[[Zone], None],
    ) -> None:
        super().__init__(master)
        self.preview = preview
        self.on_accept = on_accept
        self.geometry(format_virtual_geometry(current_virtual_desktop_bounds()))
        self.overrideredirect(True)
        self.attributes("-alpha", 0.32)
        self.attributes("-topmost", True)
        self.configure(bg="black")
        self.canvas = tk.Canvas(self, cursor="cross", bg="#203040", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.message = self.canvas.create_text(
            24, 24, anchor="nw", fill="white", font=("Segoe UI", 15, "bold"),
            text="Drag around a value. Esc cancels.",
        )
        self._start: tuple[int, int] | None = None
        self._rectangle: int | None = None
        self._zone: Zone | None = None
        self._blocking = False
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._accept())
        self.focus_force()

    def _press(self, event: tk.Event) -> None:
        self._start = (event.x_root, event.y_root)
        if self._rectangle is not None:
            self.canvas.delete(self._rectangle)
        self._rectangle = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#00ff99", width=3
        )

    def _drag(self, event: tk.Event) -> None:
        if self._start is None or self._rectangle is None:
            return
        x0, y0 = self._start
        bounds = current_virtual_desktop_bounds()
        self.canvas.coords(
            self._rectangle,
            x0 - bounds.left,
            y0 - bounds.top,
            event.x_root - bounds.left,
            event.y_root - bounds.top,
        )
        self.canvas.itemconfigure(
            self.message,
            text=f"Zone {abs(event.x_root-x0)} × {abs(event.y_root-y0)} px",
        )

    def _release(self, event: tk.Event) -> None:
        if self._start is None:
            return
        x0, y0 = self._start
        self._zone = screen_zone_from_drag((x0, y0), (event.x_root, event.y_root))
        if self._zone[2] < 8 or self._zone[3] < 8:
            self.canvas.itemconfigure(self.message, text="Zone is too small; drag again.")
            self._zone = None
            return
        try:
            text = preview_without_overlay(
                hide=self.withdraw,
                flush=self.update_idletasks,
                preview=lambda: self.preview(self._zone).strip() or "(no text)",
                restore=self.deiconify,
            )
            self.attributes("-topmost", True)
            self.focus_force()
        except Exception as exc:  # shown to the operator, picker stays open
            text = f"preview unavailable: {exc}"
        assessment = zone_preview_assessment(self._zone, text)
        self._blocking = assessment.blocking
        warning_text = "" if not assessment.warnings else "\n" + "\n".join(assessment.warnings)
        action = (
            "Drag a tighter zone; this selection cannot be accepted."
            if assessment.blocking else
            "Press Enter to use it, or drag again."
        )
        self.canvas.itemconfigure(
            self.message,
            text=f"This zone currently reads: {text}{warning_text}\n{action}",
        )

    def _accept(self) -> None:
        if self._zone is not None and not self._blocking:
            self.on_accept(self._zone)
            self.destroy()
