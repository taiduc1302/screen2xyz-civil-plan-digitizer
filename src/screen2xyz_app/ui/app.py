"""Simple wizard shell for the unified application."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .layout import APP_TITLE, HOME_MODES, WIZARD_STEPS


class Screen2XYZApp(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=24)
        self.pack(fill="both", expand=True)
        self._mode = tk.StringVar(value="")
        self._status = tk.StringVar(value="X: —   Y: —   Z: —")
        self.show_home()

    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def show_home(self) -> None:
        self._clear()
        ttk.Label(self, text=APP_TITLE, font=("Segoe UI", 22, "bold")).pack(pady=(20, 8))
        ttk.Label(self, text="Choose how you want to capture points.").pack(pady=(0, 24))
        for mode in HOME_MODES:
            ttk.Button(
                self,
                text=mode,
                width=32,
                command=lambda selected=mode: self.show_wizard(selected),
            ).pack(pady=6)

    def show_wizard(self, mode: str) -> None:
        self._mode.set(mode)
        self._clear()
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Button(header, text="← Home", command=self.show_home).pack(side="left")
        ttk.Label(header, text=mode, font=("Segoe UI", 16, "bold")).pack(side="left", padx=16)
        steps = ttk.Frame(self)
        steps.pack(fill="x", pady=24)
        for label in WIZARD_STEPS:
            ttk.Label(steps, text=label).pack(side="left", padx=8)
        ttk.Label(
            self,
            text="Choose a project folder to begin. Capture controls appear here.",
        ).pack(pady=60)
        ttk.Separator(self).pack(fill="x", side="bottom", pady=(10, 4))
        ttk.Label(self, textvariable=self._status).pack(anchor="w", side="bottom")


def run() -> None:
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("900x560")
    root.minsize(760, 460)
    Screen2XYZApp(root)
    root.mainloop()

