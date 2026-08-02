"""Bundled, offline first-run guide."""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk


def resource_root() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "screen2xyz_app" / "resources" if hasattr(sys, "_MEIPASS") else base / "resources"


def settings_path() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home())) / "Screen2XYZ"
    return root / "settings.json"


def first_run_pending(path: Path | None = None) -> bool:
    path = path or settings_path()
    if not path.is_file():
        return True
    try:
        return not bool(json.loads(path.read_text(encoding="utf-8")).get("v2_5_guide_seen"))
    except (OSError, ValueError, TypeError):
        return True


def mark_first_run_complete(path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"v2_5_guide_seen": True}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_steps() -> list[tuple[str, str, Path]]:
    root = resource_root()
    text = (root / "quickstart.md").read_text(encoding="utf-8")
    sections = [section.strip() for section in text.split("\n## ")[1:]]
    steps = []
    for index, section in enumerate(sections, start=1):
        title, _, body = section.partition("\n")
        steps.append((title.strip(), body.strip(), root / "guide" / f"step-{index}.png"))
    if len(steps) != 5:
        raise RuntimeError("bundled quick start must contain exactly five steps")
    return steps


class FirstRunGuide(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("Screen2XYZ · 5-step quick start")
        self.geometry("760x620")
        self.transient(master)
        self.steps = load_steps()
        self.index = 0
        self._photo = None
        self._title = tk.StringVar()
        self._body = tk.StringVar()
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, textvariable=self._title, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, textvariable=self._body, wraplength=700).pack(anchor="w", pady=(5, 10))
        self.image_label = ttk.Label(frame)
        self.image_label.pack(fill="both", expand=True)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        self.back = ttk.Button(buttons, text="Back", command=lambda: self._move(-1))
        self.back.pack(side="left")
        self.next = ttk.Button(buttons, text="Next", command=lambda: self._move(1))
        self.next.pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._finish)
        self._render()

    def _render(self) -> None:
        from PIL import Image, ImageTk

        title, body, image_path = self.steps[self.index]
        self._title.set(title)
        self._body.set(body)
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            image.thumbnail((700, 440))
        self._photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self._photo)
        self.back.configure(state="disabled" if self.index == 0 else "normal")
        self.next.configure(text="Finish" if self.index == len(self.steps) - 1 else "Next")

    def _move(self, delta: int) -> None:
        if self.index == len(self.steps) - 1 and delta > 0:
            self._finish()
            return
        self.index = max(0, min(len(self.steps) - 1, self.index + delta))
        self._render()

    def _finish(self) -> None:
        mark_first_run_complete()
        self.destroy()
