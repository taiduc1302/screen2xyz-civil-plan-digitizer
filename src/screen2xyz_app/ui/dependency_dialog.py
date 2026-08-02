"""Clickable install help for unavailable optional tools."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from ..dependencies import Capability


class DependencyDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, capability: Capability) -> None:
        super().__init__(master)
        self.title(f"{capability.name} is not available")
        self.transient(master)
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=capability.detail, wraplength=520).pack(anchor="w")
        ttk.Label(frame, text="Install on Windows, then restart Screen2XYZ:").pack(anchor="w", pady=(12, 3))
        command = tk.Text(frame, height=2, width=66, wrap="word")
        command.insert("1.0", capability.install_command)
        command.configure(state="disabled")
        command.pack(fill="x")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(
            buttons,
            text="Open download instructions",
            command=lambda: webbrowser.open(capability.download_url),
        ).pack(side="left")
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")
