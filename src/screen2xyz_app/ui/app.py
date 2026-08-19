"""Simple five-step Tkinter workflow for Screen2XYZ v2."""

from __future__ import annotations

import tkinter as tk
import queue
import os
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from screen2xyz_civil.models import Calibration, PixelPoint
from screen2xyz_civil.transform import build_calibration
from screen2xyz_m2.dpi import enable_pmv2

from ..backends import DefaultReader, ScreenOcrBackend
from ..capture import CapturePipeline
from ..controller import CaptureSessionController
from ..dependencies import poppler_capability, tesseract_capability
from ..hotkeys import GlobalHotkeys
from ..mapping import (
    ChannelMapping,
    ChannelSource,
    DECLARED_NUMBER_FORMATS,
    SOURCE_TYPES,
)
from ..operations import SessionOptions, ZoneHealthSnapshot
from ..plan import PlanLabelBackend, plan_click_xy, render_plan_page
from ..profiles import MappingProfileStore
from .layout import APP_TITLE, HOME_MODES, WIZARD_STEPS
from .dependency_dialog import DependencyDialog
from .guide import FirstRunGuide, first_run_pending
from .overlay import CaptureOverlay
from .review import SessionReview
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
        self._calibration: Calibration | None = None
        self._calibration_points: list[PixelPoint] | None = None
        self._known_distance = 0.0
        self._controller: CaptureSessionController | None = None
        self._overlay: CaptureOverlay | None = None
        self._review: SessionReview | None = None
        self._civil_window: tk.Toplevel | None = None
        self._screen = ScreenOcrBackend()
        self._plan_ocr = PlanLabelBackend()
        self._zones: dict[str, tuple[int, int, int, int]] = {}
        self._source_vars: dict[str, tk.StringVar] = {}
        self._value_vars: dict[str, tk.StringVar] = {}
        self._zone_labels: dict[str, tk.StringVar] = {}
        self._min_vars: dict[str, tk.StringVar] = {}
        self._max_vars: dict[str, tk.StringVar] = {}
        self._cursor_width_vars: dict[str, tk.StringVar] = {}
        self._cursor_height_vars: dict[str, tk.StringVar] = {}
        self._format_vars: dict[str, tk.StringVar] = {}
        self._precision_vars: dict[str, tk.StringVar] = {}
        self._photo = None
        self._plan_scale = 1.0
        self._status = tk.StringVar(value="X: —   Y: —   Z: —")
        self._count = tk.StringVar(value="0 rows")
        self._project_label = tk.StringVar(value="No project folder selected")
        self._source_label = tk.StringVar(value="No plan selected")
        self._delta = tk.DoubleVar(value=0.0)
        self._point_prefix = tk.StringVar(value="")
        self._point_start = tk.IntVar(value=1)
        self._allow_partial_z = tk.BooleanVar(value=False)
        self._hotkey_actions: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._hotkeys = GlobalHotkeys({
            "start/pause": lambda: self._hotkey_actions.put("toggle"),
            "stop": lambda: self._hotkey_actions.put("stop"),
            "force capture": lambda: self._hotkey_actions.put("force"),
        })
        self._hotkeys.start()
        self.after(100, self._drain_hotkeys)
        self.show_home()
        if os.environ.get("SCREEN2XYZ_SKIP_FIRST_RUN") != "1" and first_run_pending():
            self.after(250, self.show_quick_start)

    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def show_home(self) -> None:
        if self._review is not None and self._review.winfo_exists():
            self._review.destroy()
            self._review = None
        if self._controller is not None:
            self._controller.close()
            self._controller = None
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.destroy()
            self._overlay = None
        self._clear()
        ttk.Label(self, text=APP_TITLE, font=("Segoe UI", 22, "bold")).pack(pady=(28, 8))
        ttk.Label(self, text="Choose how you want to capture points.").pack(pady=(0, 24))
        for mode in HOME_MODES:
            ttk.Button(
                self, text=mode, width=32,
                command=lambda selected=mode: self._select_home_mode(selected),
            ).pack(pady=6)

    def _select_home_mode(self, mode: str) -> None:
        if mode == "Civil Plan Digitizer":
            self._open_civil_digitizer()
            return
        self.show_wizard(mode)

    def _open_civil_digitizer(self) -> None:
        """Open the retained review-first Civil workflow from the main app.

        It owns a substantial project workspace, so it receives a Toplevel
        while remaining in the same Screen2XYZ process and packaged launcher.
        The main home remains available for regular screen/PDF/image capture.
        """

        if self._civil_window is not None and self._civil_window.winfo_exists():
            self._civil_window.deiconify()
            self._civil_window.lift()
            self._civil_window.focus_force()
            return
        from screen2xyz_civil.ui.app import CivilPlanDigitizerApp

        window = tk.Toplevel(self.master)
        civil = CivilPlanDigitizerApp(window)
        self._civil_window = window

        def close() -> None:
            civil.dispose()
            if window.winfo_exists():
                window.destroy()
            if self._civil_window is window:
                self._civil_window = None

        window.protocol("WM_DELETE_WINDOW", close)
        # Keep a strong reference for the whole window lifetime; the Civil app
        # owns project state and asynchronous indexing callbacks.
        window._screen2xyz_civil_app = civil  # type: ignore[attr-defined]

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
            ttk.Button(source, text="Calibrate plan…", command=self._begin_calibration).grid(row=1, column=2, padx=4)

        mapping_frame = ttk.LabelFrame(self, text="2–3. Define zones and map columns", padding=8)
        mapping_frame.pack(fill="x", pady=5)
        for index, title in enumerate((
            "Column", "Source", "Zone / cursor box", "Value", "Minimum", "Maximum", "Number format", "Decimals"
        )):
            ttk.Label(mapping_frame, text=title, font=("Segoe UI", 9, "bold")).grid(row=0, column=index, sticky="w", padx=5)
        defaults = (
            {"x": "screen_zone_ocr", "y": "screen_zone_ocr", "z": "screen_cursor_ocr"}
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
            cursor_width = tk.StringVar(value="160")
            cursor_height = tk.StringVar(value="60")
            self._cursor_width_vars[column] = cursor_width
            self._cursor_height_vars[column] = cursor_height
            ttk.Entry(zone_box, textvariable=cursor_width, width=4).pack(side="left")
            ttk.Label(zone_box, text="×").pack(side="left")
            ttk.Entry(zone_box, textvariable=cursor_height, width=4).pack(side="left")
            value = tk.StringVar()
            self._value_vars[column] = value
            ttk.Entry(mapping_frame, textvariable=value, width=24).grid(row=row, column=3, padx=5)
            minimum = tk.StringVar()
            maximum = tk.StringVar()
            self._min_vars[column] = minimum
            self._max_vars[column] = maximum
            ttk.Entry(mapping_frame, textvariable=minimum, width=12).grid(row=row, column=4, padx=3)
            ttk.Entry(mapping_frame, textvariable=maximum, width=12).grid(row=row, column=5, padx=3)
            declared_format = tk.StringVar(value="1,234.56")
            self._format_vars[column] = declared_format
            ttk.Combobox(
                mapping_frame,
                textvariable=declared_format,
                values=DECLARED_NUMBER_FORMATS,
                state="readonly",
                width=12,
            ).grid(row=row, column=6, padx=3)
            precision = tk.StringVar(value="2")
            self._precision_vars[column] = precision
            ttk.Entry(mapping_frame, textvariable=precision, width=5).grid(
                row=row, column=7, padx=3
            )
        profile_bar = ttk.Frame(mapping_frame)
        profile_bar.grid(row=6, column=0, columnspan=8, sticky="w", pady=(8, 0))
        ttk.Button(profile_bar, text="Save profile…", command=self._save_profile).pack(side="left", padx=4)
        ttk.Button(profile_bar, text="Load profile…", command=self._load_profile).pack(side="left", padx=4)
        ttk.Button(profile_bar, text="Test mapping", command=self._test_mapping).pack(side="left", padx=4)

        policy_bar = ttk.Frame(mapping_frame)
        policy_bar.grid(row=7, column=0, columnspan=8, sticky="w", pady=(8, 0))
        ttk.Label(policy_bar, text="Minimum XY delta (m):").pack(side="left")
        ttk.Entry(policy_bar, textvariable=self._delta, width=8).pack(side="left", padx=(3, 12))
        ttk.Label(policy_bar, text="Point prefix:").pack(side="left")
        ttk.Entry(policy_bar, textvariable=self._point_prefix, width=8).pack(side="left", padx=(3, 12))
        ttk.Label(policy_bar, text="Start:").pack(side="left")
        ttk.Entry(policy_bar, textvariable=self._point_start, width=7).pack(side="left", padx=3)
        ttk.Checkbutton(
            policy_bar,
            text="Allow partial rows with missing Z (flagged)",
            variable=self._allow_partial_z,
        ).pack(side="left", padx=(12, 3))

        self._plan_canvas = tk.Canvas(self, height=210, bg="#e8edf2", highlightthickness=1)
        if mode != "Live screen capture":
            self._plan_canvas.pack(fill="both", expand=True, pady=5)
            self._plan_canvas.create_text(20, 20, anchor="nw", text="Load a plan, then click an elevation label to capture.")
            self._plan_canvas.bind("<Button-1>", self._plan_click)

        controls = ttk.LabelFrame(self, text="4–5. Capture and export", padding=8)
        controls.pack(fill="x", pady=5)
        ttk.Button(controls, text="Start", command=self._start).pack(side="left", padx=4)
        ttk.Button(controls, text="Pause / resume", command=self._hotkey_toggle).pack(side="left", padx=4)
        ttk.Button(controls, text="Stop", command=self._stop).pack(side="left", padx=4)
        ttk.Button(controls, text="Capture now", command=self._capture_now).pack(side="left", padx=4)
        ttk.Label(controls, textvariable=self._count).pack(side="left", padx=14)
        ttk.Button(controls, text="Export XLSX", command=self._export_xlsx).pack(side="right", padx=4)
        ttk.Button(controls, text="Export CSV", command=self._export_csv).pack(side="right", padx=4)
        ttk.Separator(self).pack(fill="x", pady=(5, 2))
        ttk.Label(self, textvariable=self._status, wraplength=1100).pack(anchor="w")

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
            self._calibration = None
            if self._source_path.suffix.lower() == ".pdf":
                poppler = poppler_capability()
                if not poppler.available:
                    DependencyDialog(self.master, poppler)
                    return
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
        source_type = self._source_vars[column].get()
        if source_type == "screen_cursor_ocr":
            messagebox.showinfo(
                APP_TITLE,
                "Cursor OCR follows the current Windows cursor. Adjust the width and height beside Pick.",
            )
            self._zone_labels[column].set("follows cursor")
            return
        if source_type != "screen_zone_ocr":
            messagebox.showinfo(APP_TITLE, "Choose a screen OCR source for this column first.")
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
            minimum = self._min_vars[column].get().strip()
            maximum = self._max_vars[column].get().strip()
            if bool(minimum) != bool(maximum):
                raise ValueError(f"{column} numeric range requires both minimum and maximum")
            numeric_range = (
                (float(minimum), float(maximum)) if minimum and data_type == "number" else None
            )
            channels[column] = ChannelSource(
                source_type,
                self._zones.get(column) if source_type == "screen_zone_ocr" else None,
                data_type=data_type,
                numeric_range=numeric_range,
                cursor_box_size=(
                    int(self._cursor_width_vars[column].get()),
                    int(self._cursor_height_vars[column].get()),
                ),
                declared_format=(
                    self._format_vars[column].get()
                    if data_type == "number" else None
                ),
                precision_min=(
                    int(self._precision_vars[column].get())
                    if data_type == "number" else 0
                ),
            )
        mapping = ChannelMapping(channels)
        mapping.validate()
        return mapping

    def _test_mapping(self) -> None:
        try:
            point, _observations, _crops = CapturePipeline(
                self._mapping(), DefaultReader(self._screen)
            ).read(self._context())
            messagebox.showinfo(
                APP_TITLE,
                f"Mapping test passed.\n\nX: {point.x:g}\nY: {point.y:g}\nZ: {point.z:g}",
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Mapping test failed: {exc}")

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
                self._min_vars[column].set(
                    "" if source is None or source.numeric_range is None else f"{source.numeric_range[0]:g}"
                )
                self._max_vars[column].set(
                    "" if source is None or source.numeric_range is None else f"{source.numeric_range[1]:g}"
                )
                if source is not None:
                    self._cursor_width_vars[column].set(str(source.cursor_box_size[0]))
                    self._cursor_height_vars[column].set(str(source.cursor_box_size[1]))
                    self._format_vars[column].set(
                        source.declared_format
                        or ("1.234,56" if source.decimal_separator == "comma" else "1,234.56")
                    )
                    self._precision_vars[column].set(str(source.precision_min))
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
            if self._review is not None and self._review.winfo_exists():
                self._review.destroy()
                self._review = None
            if self._controller is not None:
                self._controller.close()
                self._controller = None
            mapping = self._mapping()
            if any(
                source.source_type in {"screen_zone_ocr", "screen_cursor_ocr", "plan_label_ocr"}
                for source in mapping.channels.values()
            ):
                tesseract = tesseract_capability()
                if not tesseract.available:
                    DependencyDialog(self.master, tesseract)
                    if mapping.automatic or any(
                        source.source_type == "screen_cursor_ocr"
                        for source in mapping.channels.values()
                    ):
                        return
            if any(
                source.source_type == "plan_click"
                for source in mapping.channels.values()
            ) and self._calibration is None:
                raise ValueError("calibrate the plan before starting a plan_click session")
            self._controller = CaptureSessionController(
                self._project_dir, mapping,
                calibration=(
                    None if self._calibration is None else self._calibration.to_dict()
                ),
                on_point=self._point_added,
                on_health=self._health_updated,
                options=SessionOptions(
                    min_xy_delta=self._delta.get(),
                    point_prefix=self._point_prefix.get(),
                    point_start=self._point_start.get(),
                    allow_partial_z=self._allow_partial_z.get(),
                ),
            )
            if mapping.automatic:
                self._controller.start_auto()
                self._status.set("Automatic capture running; stable changed values are retained.")
            else:
                self._status.set("Click capture ready. Click the plan or use Capture now.")
            if self._overlay is not None and self._overlay.winfo_exists():
                self._overlay.destroy()
            self._overlay = CaptureOverlay(
                self.master,
                on_pause=self._hotkey_toggle,
                on_stop=self._stop,
                on_repick=self._repick_zones,
            )
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
            point = PixelPoint(event.x / self._plan_scale, event.y / self._plan_scale)
            if self._calibration_points is not None:
                self._calibration_click(point)
                return
            if self._controller is None:
                self._start()
            assert self._controller is not None
            context = self._context()
            mapping = self._controller.mapping
            if mapping.channels["z"].source_type == "plan_label_ocr":
                z, confidence, raw = self._plan_ocr.read_nearest(self._rendered_path, point)
                context["z"] = z
                context["z_confidence"] = confidence
                self._value_vars["z"].set(raw)
            if any(mapping.channels[name].source_type == "plan_click" for name in ("x", "y")):
                if self._calibration is None:
                    raise ValueError("calibrate the plan before using plan_click")
                east, north = plan_click_xy(point, self._calibration)
                if mapping.channels["x"].source_type == "plan_click":
                    context["x"] = east
                if mapping.channels["y"].source_type == "plan_click":
                    context["y"] = north
            self._controller.capture_click(context)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _point_added(self, point, count: int) -> None:
        self.after(0, lambda: self._show_point(point, count))

    def _health_updated(self, snapshot: ZoneHealthSnapshot) -> None:
        self.after(0, lambda: self._show_health(snapshot))

    def _show_health(self, snapshot: ZoneHealthSnapshot) -> None:
        self._status.set(snapshot.message)
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.show_health(snapshot)

    def _begin_calibration(self) -> None:
        if self._rendered_path is None:
            messagebox.showinfo(APP_TITLE, "Load a PDF or image before calibration.")
            return
        self._calibration_points = []
        self._status.set("Calibration: click the first endpoint of a known distance.")

    def _calibration_click(self, point: PixelPoint) -> None:
        assert self._calibration_points is not None
        self._calibration_points.append(point)
        count = len(self._calibration_points)
        if count == 1:
            self._status.set("Calibration: click the second endpoint of the known distance.")
            return
        if count == 2:
            value = simpledialog.askfloat(
                APP_TITLE, "Known distance between the two points (metres):",
                minvalue=0.000001,
            )
            if value is None:
                self._calibration_points = None
                self._status.set("Calibration cancelled.")
                return
            self._known_distance = value
            self._status.set("Calibration: click the local coordinate origin.")
            return
        if count == 3:
            self._status.set("Calibration: click any point in the positive East direction.")
            return
        origin_east = simpledialog.askfloat(
            APP_TITLE, "Origin Easting (metres):", initialvalue=0.0
        )
        origin_north = simpledialog.askfloat(
            APP_TITLE, "Origin Northing (metres):", initialvalue=0.0
        )
        if origin_east is None or origin_north is None:
            self._calibration_points = None
            self._status.set("Calibration cancelled.")
            return
        points = self._calibration_points
        self._calibration = build_calibration(
            revision=1,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            scale_point_1=points[0], scale_point_2=points[1],
            known_distance_m=self._known_distance,
            origin_pixel=points[2], east_reference=points[3],
            origin_east_m=origin_east, origin_north_m=origin_north,
        )
        self._calibration_points = None
        self._status.set(
            f"Calibration ready: {self._calibration.metres_per_pixel:g} metres/pixel."
        )

    def _show_point(self, point, count: int) -> None:
        self._count.set(f"{count} rows")
        z_text = "MISSING (PARTIAL)" if point.z is None else f"{point.z:g}"
        self._status.set(f"X: {point.x:g}   Y: {point.y:g}   Z: {z_text}")
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.show_point(point, count)

    def _hotkey_toggle(self) -> None:
        try:
            if self._controller is None or self._controller.stopped:
                self._start()
            elif self._controller.auto is not None:
                self._controller.toggle_pause()
                self._status.set(
                    "Capture paused." if self._controller.paused else "Capture resumed."
                )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _drain_hotkeys(self) -> None:
        try:
            while True:
                action = self._hotkey_actions.get_nowait()
                if action == "toggle":
                    self._hotkey_toggle()
                elif action == "stop":
                    self._stop()
                elif action == "force":
                    self._force_capture()
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._drain_hotkeys)

    def _force_capture(self) -> None:
        try:
            if self._controller is None:
                self._start()
            assert self._controller is not None
            self._controller.force_capture()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _repick_zones(self) -> None:
        columns = [
            name for name, source in self._mapping().channels.items()
            if source.source_type == "screen_zone_ocr"
        ]
        if self._controller is not None:
            self._controller.pause()

        def pick(index: int) -> None:
            if index >= len(columns):
                if self._controller is None:
                    self._start()
                else:
                    self._controller.reconfigure(self._mapping())
                    self._status.set("Zones updated; capture resumed in the same session.")
                return
            column = columns[index]

            def accept(zone) -> None:
                self._zones[column] = zone
                self._zone_labels[column].set(
                    f"{zone[0]},{zone[1]} {zone[2]}×{zone[3]}"
                )
                pick(index + 1)

            ZonePicker(
                self.master,
                preview=lambda zone: self._screen.read_zone(zone).raw_text,
                on_accept=accept,
            )

        pick(0)

    def _stop(self) -> None:
        if self._controller is not None and not self._controller.stopped:
            self._controller.stop()
            self._status.set("Capture stopped.")
            if self._overlay is not None and self._overlay.winfo_exists():
                self._overlay.destroy()
                self._overlay = None
            if self._review is not None and self._review.winfo_exists():
                self._review.destroy()
            self._review = SessionReview(
                self.master,
                self._controller,
                export_xlsx=self._export_xlsx,
                export_csv=self._export_csv,
            )

    def shutdown(self) -> None:
        self._hotkeys.stop()
        if self._controller is not None:
            self._controller.close()
        self.master.destroy()

    def show_quick_start(self) -> None:
        FirstRunGuide(self.master)

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
    root.protocol("WM_DELETE_WINDOW", app.shutdown)
    menu = tk.Menu(root)
    export_menu = tk.Menu(menu, tearoff=False)
    export_menu.add_command(
        label="Advanced estimator export…", command=app.advanced_export
    )
    menu.add_cascade(label="Export", menu=export_menu)
    help_menu = tk.Menu(menu, tearoff=False)
    help_menu.add_command(label="5-step quick start", command=app.show_quick_start)
    menu.add_cascade(label="Help", menu=help_menu)
    root.configure(menu=menu)
    root.mainloop()
