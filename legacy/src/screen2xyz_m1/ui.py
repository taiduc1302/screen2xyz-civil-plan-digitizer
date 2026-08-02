"""Minimal Tkinter review interface for the M1 lab.

Standard-library only. Every consequential action — selecting a file,
processing it, correcting, approving, rejecting, exporting — is an explicit
button press. Nothing is approved or exported automatically, and the
optional external-AI assistant is disabled by default and clearly labelled.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .assist import AssistRequest, NullAssistant
from .session import PENDING, ReviewSession, SessionError


class ReviewApp:
    def __init__(self, repository_root: Path, run_root: Path) -> None:
        self.repository_root = repository_root
        run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
        self.session = ReviewSession(repository_root, run_root, run_id)
        self.assistant = NullAssistant()

        self.root = tk.Tk()
        self.root.title(f"Screen2XYZ M1 review — {run_id}")
        self.root.geometry("1080x640")

        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="Select PNG…", command=self.select_and_process).pack(side="left")
        ttk.Button(top, text="Export approved", command=self.export_approved).pack(side="left", padx=6)
        self.status = tk.StringVar(
            value=f"Run: {run_id} — outputs under .lab_work/m1_runs/{run_id}/ — External AI: not used"
        )
        ttk.Label(top, textvariable=self.status).pack(side="left", padx=10)

        columns = ("id", "source", "lat", "lon", "elev", "state", "codes", "decision")
        self.table = ttk.Treeview(self.root, columns=columns, show="headings", height=12)
        widths = (50, 220, 110, 110, 90, 90, 220, 90)
        for column, width in zip(columns, widths):
            self.table.heading(column, text=column.upper())
            self.table.column(column, width=width, anchor="w")
        self.table.pack(fill="both", expand=True, padx=6)
        self.table.bind("<<TreeviewSelect>>", lambda _e: self.show_detail())

        detail = ttk.Frame(self.root, padding=6)
        detail.pack(fill="x")
        ttk.Label(detail, text="Raw OCR (immutable):").grid(row=0, column=0, sticky="w")
        self.raw_var = tk.StringVar()
        ttk.Label(detail, textvariable=self.raw_var, wraplength=1000).grid(
            row=1, column=0, columnspan=8, sticky="w"
        )
        self.entries: dict[str, tk.Entry] = {}
        for index, (label, key) in enumerate(
            (("LAT", "lat"), ("LON", "lon"), ("ELEV (m)", "elev"))
        ):
            ttk.Label(detail, text=label).grid(row=2, column=index * 2, sticky="e", padx=4)
            entry = ttk.Entry(detail, width=16)
            entry.grid(row=2, column=index * 2 + 1, sticky="w")
            self.entries[key] = entry
        buttons = ttk.Frame(detail)
        buttons.grid(row=3, column=0, columnspan=8, sticky="w", pady=6)
        ttk.Button(buttons, text="Apply correction", command=self.apply_correction).pack(side="left")
        ttk.Button(buttons, text="Approve", command=self.approve).pack(side="left", padx=6)
        ttk.Button(buttons, text="Reject", command=self.reject).pack(side="left")
        ttk.Button(buttons, text="Assist note", command=self.assist_note).pack(side="left", padx=6)

    # -- helpers ---------------------------------------------------------

    def selected_id(self) -> str | None:
        selection = self.table.selection()
        return selection[0] if selection else None

    def refresh(self) -> None:
        existing = set(self.table.get_children())
        for candidate in self.session.candidates():
            row = (
                candidate.candidate_id,
                candidate.source_name,
                candidate.effective_latitude,
                candidate.effective_longitude,
                candidate.effective_elevation_m,
                candidate.classification or "-",
                "|".join(candidate.correction_codes or candidate.validation_codes),
                candidate.decision,
            )
            if candidate.candidate_id in existing:
                self.table.item(candidate.candidate_id, values=row)
            else:
                self.table.insert("", "end", iid=candidate.candidate_id, values=row)

    def show_detail(self) -> None:
        candidate_id = self.selected_id()
        if not candidate_id:
            return
        for candidate in self.session.candidates():
            if candidate.candidate_id == candidate_id:
                self.raw_var.set(candidate.raw_text.replace("\n", " ⏎ ") or "(no OCR text)")
                for key, value in (
                    ("lat", candidate.effective_latitude),
                    ("lon", candidate.effective_longitude),
                    ("elev", candidate.effective_elevation_m),
                ):
                    self.entries[key].delete(0, "end")
                    self.entries[key].insert(0, value)
                return

    # -- actions ---------------------------------------------------------

    def select_and_process(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select a PNG to process", filetypes=[("PNG images", "*.png")]
        )
        if not filename:
            return
        try:
            candidate = self.session.process_image(Path(filename))
        except Exception as exc:
            messagebox.showerror("Intake rejected", str(exc))
            return
        self.refresh()
        self.status.set(
            f"Processed {candidate.source_name} "
            f"(sha256 {candidate.source_sha256[:12]}…) — decide, then export"
        )

    def apply_correction(self) -> None:
        candidate_id = self.selected_id()
        if not candidate_id:
            return
        try:
            self.session.correct(
                candidate_id,
                self.entries["lat"].get().strip(),
                self.entries["lon"].get().strip(),
                self.entries["elev"].get().strip(),
            )
        except SessionError as exc:
            messagebox.showerror("Correction rejected", str(exc))
        self.refresh()

    def approve(self) -> None:
        candidate_id = self.selected_id()
        if not candidate_id:
            return
        try:
            self.session.approve(candidate_id)
        except SessionError as exc:
            messagebox.showerror("Cannot approve", str(exc))
        self.refresh()

    def reject(self) -> None:
        candidate_id = self.selected_id()
        if not candidate_id:
            return
        try:
            self.session.reject(candidate_id)
        except SessionError as exc:
            messagebox.showerror("Cannot reject", str(exc))
        self.refresh()

    def assist_note(self) -> None:
        candidate_id = self.selected_id()
        if not candidate_id:
            return
        for candidate in self.session.candidates():
            if candidate.candidate_id == candidate_id:
                result = self.assistant.review_note(
                    AssistRequest(
                        raw_text_display=candidate.raw_text,
                        parsed_latitude=candidate.parsed_latitude,
                        parsed_longitude=candidate.parsed_longitude,
                        parsed_elevation_m=candidate.parsed_elevation_m,
                        reason_codes=candidate.validation_codes,
                    )
                )
                messagebox.showinfo("Assist note", result.note)
                return

    def export_approved(self) -> None:
        pending = [c for c in self.session.candidates() if c.decision == PENDING]
        if pending and not messagebox.askyesno(
            "Pending candidates",
            f"{len(pending)} candidate(s) are still pending and will NOT be exported. Continue?",
        ):
            return
        summary = self.session.export_approved()
        self.status.set(
            f"Exported {summary['approved_count']} approved candidate(s) to "
            f".lab_work/m1_runs/{self.session.run_id}/ — External AI: "
            f"{'used' if summary['external_ai_used'] else 'not used'}"
        )
        messagebox.showinfo(
            "Export complete",
            f"Approved: {summary['approved_count']}\nRejected: {summary['rejected_count']}\n"
            f"Pending (not exported): {summary['pending_count']}\n"
            f"Output: .lab_work/m1_runs/{self.session.run_id}/",
        )

    def run(self) -> None:
        self.root.mainloop()


def launch(repository_root: Path, run_root: Path) -> None:
    ReviewApp(repository_root, run_root).run()
