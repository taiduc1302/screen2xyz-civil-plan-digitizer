"""Session review table with audited edit/delete actions."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, simpledialog, ttk

from ..controller import CaptureSessionController


class SessionReview(tk.Toplevel):
    COLUMNS = ("point_number", "x", "y", "z", "description", "created_utc")

    def __init__(
        self,
        master: tk.Misc,
        controller: CaptureSessionController,
        *,
        export_xlsx: Callable[[], None],
        export_csv: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.controller = controller
        self.title("Review captured points")
        self.geometry("860x430")
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        self.filter_text = tk.StringVar()
        ttk.Label(body, text="Filter:").pack(side="top", anchor="w")
        entry = ttk.Entry(body, textvariable=self.filter_text)
        entry.pack(fill="x", pady=(0, 6))
        self.tree = ttk.Treeview(body, columns=self.COLUMNS, show="headings")
        for name in self.COLUMNS:
            self.tree.heading(
                name,
                text=name.replace("_", " ").title(),
                command=lambda field=name: self.refresh(sort_by=field),
            )
            self.tree.column(name, width=120, anchor="w")
        self.tree.pack(fill="both", expand=True)
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Edit selected…", command=self.edit_selected).pack(side="left")
        ttk.Button(actions, text="Delete selected", command=self.delete_selected).pack(side="left", padx=5)
        ttk.Button(actions, text="Re-export XLSX", command=export_xlsx).pack(side="right")
        ttk.Button(actions, text="Re-export CSV", command=export_csv).pack(side="right", padx=5)
        self.filter_text.trace_add("write", lambda *_args: self.refresh())
        self.refresh()

    def refresh(self, *, sort_by: str = "id") -> None:
        needle = self.filter_text.get().casefold()
        rows = list(self.controller.points())
        rows.sort(key=lambda row: (row[sort_by] is None, row[sort_by]))
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            values = tuple(row[name] for name in self.COLUMNS)
            if needle and needle not in " ".join(str(value) for value in values).casefold():
                continue
            self.tree.insert("", "end", iid=str(row["id"]), values=values)

    def _selected_id(self) -> int | None:
        selected = self.tree.selection()
        return None if not selected else int(selected[0])

    def edit_selected(self) -> None:
        point_id = self._selected_id()
        if point_id is None:
            return
        row = next(row for row in self.controller.points() if row["id"] == point_id)
        changes: dict[str, object] = {}
        for name in ("x", "y", "z"):
            value = simpledialog.askfloat(
                "Edit captured point", name.upper(), initialvalue=float(row[name]), parent=self
            )
            if value is None:
                return
            changes[name] = value
        description = simpledialog.askstring(
            "Edit captured point", "Description", initialvalue=row["description"] or "", parent=self
        )
        if description is None:
            return
        changes["description"] = description
        self.controller.edit_point(point_id, changes)
        self.refresh()

    def delete_selected(self) -> None:
        point_id = self._selected_id()
        if point_id is None:
            return
        if messagebox.askyesno(
            "Delete captured point",
            "Hide this point from exports? The original and deletion audit are retained.",
            parent=self,
        ):
            self.controller.delete_point(point_id)
            self.refresh()
