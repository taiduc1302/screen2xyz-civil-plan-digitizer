"""Fullscreen rectangle picker with OCR preview callback."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

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
        self.attributes("-fullscreen", True)
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
        self.canvas.coords(self._rectangle, x0, y0, event.x_root, event.y_root)
        self.canvas.itemconfigure(
            self.message,
            text=f"Zone {abs(event.x_root-x0)} × {abs(event.y_root-y0)} px",
        )

    def _release(self, event: tk.Event) -> None:
        if self._start is None:
            return
        x0, y0 = self._start
        left, top = min(x0, event.x_root), min(y0, event.y_root)
        self._zone = (left, top, abs(event.x_root - x0), abs(event.y_root - y0))
        if self._zone[2] < 8 or self._zone[3] < 8:
            self.canvas.itemconfigure(self.message, text="Zone is too small; drag again.")
            self._zone = None
            return
        try:
            text = self.preview(self._zone).strip() or "(no text)"
        except Exception as exc:  # shown to the operator, picker stays open
            text = f"preview unavailable: {exc}"
        self.canvas.itemconfigure(
            self.message,
            text=f"This zone currently reads: {text}\nPress Enter to use it, or drag again.",
        )

    def _accept(self) -> None:
        if self._zone is not None:
            self.on_accept(self._zone)
            self.destroy()

