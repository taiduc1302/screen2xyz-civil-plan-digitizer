"""Simple five-step Tkinter workflow for Screen2XYZ v2."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from screen2xyz_civil.models import PixelPoint
from screen2xyz_m2.dpi import enable_pmv2

from ..backends import ScreenOcrBackend
from ..controller import CaptureSessionController
from ..mapping import ChannelMapping, ChannelSource, SOURCE_TYPES
from ..plan import PlanLabelBackend, render_plan_page
from ..profiles import MappingProfileStore
from .layout import APP_TITLE, HOME_MODES, WIZARD_STEPS
from .zone_picker import ZonePicker


class Screen2XYZApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=18)
        self.master = master
        self.pack(fill="both", expand=True)
        self._mode = ""
        self._project_dir: Path | None = None
        self._source_path: Path | None = None
        self._rendered_path: Path | None = None
        self._controller: CaptureSessionController | None = None
        self._screen = ScreenOcrBackend()
        self._plan_ocr = PlanLabelBackend()
        self._zones: dict[str, tuple[int, int, int, int]] = {}
        self._source_vars: dict[str, tk.StringVar] = {}
        self._value_vars: dict[str, tk.StringVar] = {}
        self._zone_labels: dict[str, tk.StringVar] = {}
        self._photo = None
        self._plan_scale = 1.0
        self._status = tk.StringVar(value="X: —   Y: —   Z: —")
        self._count = tk.StringVar(value="0 rows")
        self._project_label = tk.StringVar(value="No project folder selected")
        self._source_label = tk.StringVar(value="No plan selected")
        self.show_home()

    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def show_home(self) -> None:
        if self._controller is not None:
            self._controller.close()
            self._controller = None
        self._clear()
        ttk.Label(self, text=APP_TITLE, font=("Segoe UI", 22, "bold")).pack(pady=(28, 8))
        ttk.Label(self, text="Choose how you want to capture points.").pack(pady=(0, 24))
        for mode in HOME_MODES:
            ttk.Button(
                self, text=mode, width=32,
                command=lambda selected=mode: self.show_wizard(selected),
            ).pack(pady=6)

    def show_wizard(self, mode: str) -> None:
        self._mode = mode
        self._zones.clear()
        self._clear()
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Button(header, text="← Home", command=self.show_home).pack(side="left")
        ttk.Label(header, text=mode, font=("Segoe UI", 16, "bold")).pack(side="left", padx=14)
        for label in WIZARD_STEPS:
            ttk.Label(header, text=label).pack(side="left", padx=5)

        source = ttk.LabelFrame(self, text="1. Pick source", padding=8)
        source.pack(fill="x", pady=(14, 5))
        ttk.Button(source, text="Project folder…", command=self._choose_project).grid(row=0, column=0, padx=4)
        ttk.Label(source, textvariable=self._project_label).grid(row=0, column=1, sticky="w")
        if mode != "Live screen capture":
            ttk.Button(source, text="Choose plan…", command=self._choose_plan).grid(row=1, column=0, padx=4, pady=4)
            ttk.Label(source, textvariable=self._source_label).grid(row=1, column=1, sticky="w")

        mapping_frame = ttk.LabelFrame(self, text="2–3. Define zones and map columns", padding=8)
        mapping_frame.pack(fill="x", pady=5)
        for index, title in enumerate(("Column", "Source", "Zone", "Capture-time value")):
            ttk.Label(mapping_frame, text=title, font=("Segoe UI", 9, "bold")).grid(row=0, column=index, sticky="w", padx=5)
        defaults = (
            {"x": "screen_zone_ocr", "y": "screen_zone_ocr", "z": "screen_zone_ocr"}
            if mode == "Live screen capture"
            else {"x": "screen_zone_ocr", "y": "screen_zone_ocr", "z": "plan_label_ocr"}
        )
        choices = ("(not used)",) + SOURCE_TYPES
        for row, column in enumerate(("x", "y", "z", "description", "point_number"), start=1):
            ttk.Label(mapping_frame, text=column.replace("_", " ").title()).grid(row=row, column=0, sticky="w", padx=5)
            variable = tk.StringVar(value=defaults.get(column, "(not used)"))
            self._source_vars[column] = variable
            ttk.Combobox(mapping_frame, textvariable=variable, values=choices, state="readonly", width=20).grid(row=row, column=1, padx=5)
            zone_label = tk.StringVar(value="not set")
            self._zone_labels[column] = zone_label
            zone_box = ttk.Frame(mapping_frame)
            zone_box.grid(row=row, column=2, sticky="w")
            ttk.Button(zone_box, text="Pick", command=lambda name=column: self._pick_zone(name)).pack(side="left")
            ttk.Label(zone_box, textvariable=zone_label, width=20).pack(side="left", padx=4)
            value = tk.StringVar()
            self._value_vars[column] = value
            ttk.Entry(mapping_frame, textvariable=value, width=24).grid(row=row, column=3, padx=5)
        profile_bar = ttk.Frame(mapping_frame)
        profile_bar.grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(profile_bar, text="Save profile…", command=self._save_profile).pack(side="left", padx=4)
        ttk.Button(profile_bar, text="Load profile…", command=self._load_profile).pack(side="left", padx=4)

        self._plan_canvas = tk.Canvas(self, height=210, bg="#e8edf2", highlightthickness=1)
        if mode != "Live screen capture":
            self._plan_canvas.pack(fill="both", expand=True, pady=5)
            self._plan_canvas.create_text(20, 20, anchor="nw", text="Load a plan, then click an elevation label to capture.")
            self._plan_canvas.bind("<Button-1>", self._plan_click)

        controls = ttk.LabelFrame(self, text="4–5. Capture and export", padding=8)
        controls.pack(fill="x", pady=5)
        ttk.Button(controls, text="Start", command=self._start).pack(side="left", padx=4)
        ttk.Button(controls, text="Stop", command=self._stop).pack(side="left", padx=4)
        ttk.Button(controls, text="Capture now", command=self._capture_now).pack(side="left", padx=4)
        ttk.Label(controls, textvariable=self._count).pack(side="left", padx=14)
        ttk.Button(controls, text="Export XLSX", command=self._export_xlsx).pack(side="right", padx=4)
        ttk.Button(controls, text="Export CSV", command=self._export_csv).pack(side="right", padx=4)
        ttk.Separator(self).pack(fill="x", pady=(5, 2))
        ttk.Label(self, textvariable=self._status).pack(anchor="w")

    def _choose_project(self) -> None:
        value = filedialog.askdirectory(title="Choose Screen2XYZ project folder")
        if value:
            self._project_dir = Path(value)
            self._project_label.set(str(self._project_dir))

    def _choose_plan(self) -> None:
        value = filedialog.askopenfilename(
            title="Choose plan",
            filetypes=(("Plans", "*.pdf *.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")),
        )
        if not value:
            return
        try:
            self._source_path = Path(value)
            if self._source_path.suffix.lower() == ".pdf":
                if self._project_dir is None:
                    raise ValueError("choose a project folder before rendering a PDF")
                self._rendered_path = render_plan_page(
                    self._source_path, self._project_dir / ".screen2xyz" / "rendered"
                )
            else:
                self._rendered_path = self._source_path
            self._source_label.set(str(self._source_path))
            self._show_plan()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _show_plan(self) -> None:
        from PIL import Image, ImageTk

        assert self._rendered_path is not None
        with Image.open(self._rendered_path) as source:
            image = source.convert("RGB")
        width = max(1, self._plan_canvas.winfo_width())
        height = max(1, self._plan_canvas.winfo_height())
        self._plan_scale = min(width / image.width, height / image.height, 1.0)
        display = image.resize(
            (max(1, int(image.width * self._plan_scale)), max(1, int(image.height * self._plan_scale)))
        )
        self._photo = ImageTk.PhotoImage(display)
        self._plan_canvas.delete("all")
        self._plan_canvas.create_image(0, 0, anchor="nw", image=self._photo)

    def _pick_zone(self, column: str) -> None:
        if self._source_vars[column].get() != "screen_zone_ocr":
            messagebox.showinfo(APP_TITLE, "Choose screen_zone_ocr for this column first.")
            return
        def accept(zone):
            self._zones[column] = zone
            self._zone_labels[column].set(f"{zone[0]},{zone[1]} {zone[2]}×{zone[3]}")
        ZonePicker(
            self.master,
            preview=lambda zone: self._screen.read_zone(zone).raw_text,
            on_accept=accept,
        )

    def _mapping(self) -> ChannelMapping:
        channels = {}
        for column, variable in self._source_vars.items():
            source_type = variable.get()
            if source_type == "(not used)":
                continue
            data_type = "text" if column in {"description", "point_number"} else "number"
            channels[column] = ChannelSource(
                source_type,
                self._zones.get(column) if source_type == "screen_zone_ocr" else None,
                data_type=data_type,
            )
        mapping = ChannelMapping(channels)
        mapping.validate()
        return mapping

    def _save_profile(self) -> None:
        try:
            if self._project_dir is None:
                raise ValueError("choose a project folder first")
            name = simpledialog.askstring(APP_TITLE, "Profile name:")
            if name:
                MappingProfileStore(self._project_dir).save(name, self._mapping())
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _load_profile(self) -> None:
        try:
            if self._project_dir is None:
                raise ValueError("choose a project folder first")
            store = MappingProfileStore(self._project_dir)
            name = simpledialog.askstring(APP_TITLE, "Profile name:\n" + "\n".join(store.names()))
            if not name:
                return
            mapping = store.load(name)
            self._zones.clear()
            for column in self._source_vars:
                source = mapping.channels.get(column)
                self._source_vars[column].set("(not used)" if source is None else source.source_type)
                if source is not None and source.zone is not None:
                    self._zones[column] = source.zone
                    self._zone_labels[column].set(
                        f"{source.zone[0]},{source.zone[1]} {source.zone[2]}×{source.zone[3]}"
                    )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _start(self) -> None:
        try:
            if self._project_dir is None:
                raise ValueError("choose a project folder first")
            if self._controller is not None:
                self._controller.close()
                self._controller = None
            mapping = self._mapping()
            self._controller = CaptureSessionController(
                self._project_dir, mapping, on_point=self._point_added
            )
            if mapping.automatic:
                self._controller.start_auto()
                self._status.set("Automatic capture running; stable changed values are retained.")
            else:
                self._status.set("Click capture ready. Click the plan or use Capture now.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _context(self) -> dict[str, Any]:
        return {
            column: variable.get()
            for column, variable in self._value_vars.items()
            if variable.get() != ""
        }

    def _capture_now(self) -> None:
        try:
            if self._controller is None:
                self._start()
            assert self._controller is not None
            self._controller.capture_click(self._context())
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _plan_click(self, event: tk.Event) -> None:
        try:
            if self._rendered_path is None:
                raise ValueError("load a PDF or image first")
            if self._controller is None:
                self._start()
            assert self._controller is not None
            point = PixelPoint(event.x / self._plan_scale, event.y / self._plan_scale)
            context = self._context()
            mapping = self._controller.mapping
            if mapping.channels["z"].source_type == "plan_label_ocr":
                z, confidence, raw = self._plan_ocr.read_nearest(self._rendered_path, point)
                context["z"] = z
                context["z_confidence"] = confidence
                self._value_vars["z"].set(raw)
            if any(mapping.channels[name].source_type == "plan_click" for name in ("x", "y")):
                raise ValueError("plan_click X/Y requires a saved calibration profile")
            self._controller.capture_click(context)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _point_added(self, point, count: int) -> None:
        self.after(0, lambda: self._show_point(point, count))

    def _show_point(self, point, count: int) -> None:
        self._count.set(f"{count} rows")
        self._status.set(f"X: {point.x:g}   Y: {point.y:g}   Z: {point.z:g}")

    def _stop(self) -> None:
        if self._controller is not None:
            self._controller.stop()
            self._status.set("Capture stopped.")

    def _export_xlsx(self) -> None:
        self._export("xlsx")

    def _export_csv(self) -> None:
        self._export("csv")

    def _export(self, kind: str) -> None:
        try:
            if self._controller is None:
                raise ValueError("start a session before exporting")
            path = filedialog.asksaveasfilename(
                title=f"Export {kind.upper()}", defaultextension=f".{kind}",
                filetypes=((kind.upper(), f"*.{kind}"),),
            )
            if path:
                result = (
                    self._controller.export_xlsx(Path(path))
                    if kind == "xlsx" else self._controller.export_csv(Path(path))
                )
                messagebox.showinfo(APP_TITLE, f"Exported {result}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def advanced_export(self) -> None:
        try:
            if self._controller is None:
                raise ValueError("start a session before exporting")
            path = filedialog.askdirectory(title="Advanced estimator export folder")
            if path:
                result = self._controller.advanced_export(Path(path))
                messagebox.showinfo(
                    APP_TITLE, f"Advanced export created in {result['export_dir']}"
                )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))


def run() -> None:
    enable_pmv2()
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("1080x760")
    root.minsize(900, 650)
    app = Screen2XYZApp(root)
    menu = tk.Menu(root)
    export_menu = tk.Menu(menu, tearoff=False)
    export_menu.add_command(
        label="Advanced estimator export…", command=app.advanced_export
    )
    menu.add_cascade(label="Export", menu=export_menu)
    root.configure(menu=menu)
    root.mainloop()
