"""Estimator-facing Tk workspace for the Civil Plan Digitizer."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from .. import PRELIMINARY_WARNING
from .. import contracts as C
from ..exports import ExportError, export_handoff
from ..detection import detect_symbols
from ..models import CivilPoint, CropRegion, PixelPoint
from ..ocr import OcrAdapterError, WindowsOcrAdapter
from ..pdf import (
    PdfAdapterError,
    extract_pdf_text_candidates,
    extract_pdf_vector_shapes,
    inspect_pdf,
    render_pdf_page,
)
from ..persistence import (
    ProjectPersistenceError,
    load_project,
    save_project,
)
from ..qa import qa_summary
from ..source import inspect_png
from ..surface import SurfaceError, build_project_surface, cut_fill_preview
from ..workflow import CivilWorkflow, WorkflowError, new_project
from .layout import (
    canvas_to_source,
    manual_type,
    next_zoom,
    point_color,
    source_to_canvas,
    zoom_operation,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CivilPlanDigitizerApp:
    """One local civil project at a time; no network and no auto approval."""

    def __init__(self, root: tk.Tk | None = None) -> None:
        self.root = root or tk.Tk()
        self.root.title("Screen2XYZ — Civil Plan Digitizer")
        self.root.geometry("1420x900")
        self.root.minsize(1100, 700)

        self.project = None
        self.workflow: CivilWorkflow | None = None
        self.project_path: Path | None = None
        self.source_path: Path | None = None
        self.display_source_path: Path | None = None
        self.pdf_page_index = 0
        self.render_dpi = 150
        self.original_image: tk.PhotoImage | None = None
        self.display_image: tk.PhotoImage | None = None
        self.preview_image: tk.PhotoImage | None = None
        self.zoom = 1.0
        self._tool = "select"
        self._crop_start: PixelPoint | None = None
        self._drag_rect: int | None = None
        self._collector: list[PixelPoint] = []
        self._collect_count = 0
        self._collect_callback: Callable[[list[PixelPoint]], None] | None = None
        self._manual_payload: tuple[float, str] | None = None

        self.status = tk.StringVar(value="Open a local PDF or PNG to begin.")
        self.calibration_status = tk.StringVar(value="Calibration: not set")
        self.selected_reason = tk.StringVar(value="Select a point to review.")
        self._build()
        self._bind_shortcuts()

    def _build(self) -> None:
        nav = ttk.Frame(self.root, padding=(8, 6))
        nav.pack(fill="x")
        ttk.Label(
            nav,
            text="Screen2XYZ",
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left")
        ttk.Label(
            nav,
            text="  Terrain Capture  |  Civil Plan Digitizer  |  Projects  |  Exports",
        ).pack(side="left")
        ttk.Button(nav, text="Help", command=self._show_help).pack(side="right")

        warning = tk.Label(
            self.root,
            text=PRELIMINARY_WARNING,
            bg="#7f1d1d",
            fg="white",
            padx=8,
            pady=6,
            anchor="w",
        )
        warning.pack(fill="x")

        files = ttk.Frame(self.root, padding=(8, 6))
        files.pack(fill="x")
        for label, command in (
            ("New from PDF/PNG…", self.new_from_source),
            ("Open project…", self.open_project),
            ("Save project", self.save_project),
            ("Save as…", lambda: self.save_project(save_as=True)),
            ("Export reviewed package…", self.export_reviewed),
        ):
            ttk.Button(files, text=label, command=command).pack(
                side="left", padx=(0, 5)
            )
        ttk.Label(files, textvariable=self.status).pack(side="left", padx=8)

        tools = ttk.Frame(self.root, padding=(8, 0, 8, 6))
        tools.pack(fill="x")
        for label, command in (
            ("Select crop", self.begin_crop),
            ("Calibrate scale/origin/East", self.begin_calibration),
            ("Verify second distance", self.begin_scale_check),
            ("Add manual point", self.begin_manual_point),
            ("Move selected", self.begin_move_point),
            ("Extract PDF text", self.extract_pdf_candidates),
            ("Run local OCR", self.run_local_ocr),
            ("QA summary", self.show_qa),
            ("Zoom −", lambda: self.change_zoom(-1)),
            ("Zoom +", lambda: self.change_zoom(1)),
            ("Fit 100%", self.reset_zoom),
        ):
            ttk.Button(tools, text=label, command=command).pack(
                side="left", padx=(0, 5)
            )
        ttk.Label(tools, textvariable=self.calibration_status).pack(
            side="right", padx=8
        )

        geometry = ttk.Frame(self.root, padding=(8, 0, 8, 6))
        geometry.pack(fill="x")
        ttk.Label(geometry, text="Surface constraints:").pack(side="left")
        for label, command in (
            ("Set boundary", lambda: self.begin_geometry("boundary")),
            ("Add exclusion", lambda: self.begin_geometry("exclusion")),
            ("Add breakline", lambda: self.begin_geometry("breakline")),
            ("Add no-cross line", lambda: self.begin_geometry("no_cross")),
            ("Preview Existing TIN", lambda: self.show_surface(C.EXISTING_GROUND)),
            ("Preview Design TIN", lambda: self.show_surface(C.DESIGN_GRADE)),
            ("Cut/fill samples", self.show_cut_fill),
            ("Enable preliminary LandXML", self.enable_landxml),
        ):
            ttk.Button(geometry, text=label, command=command).pack(
                side="left", padx=(5, 0)
            )

        vertical = ttk.Panedwindow(self.root, orient="vertical")
        vertical.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        upper = ttk.Panedwindow(vertical, orient="horizontal")
        vertical.add(upper, weight=4)

        canvas_frame = ttk.Frame(upper)
        upper.add(canvas_frame, weight=4)
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#20242a",
            highlightthickness=0,
            cursor="crosshair",
        )
        xscroll = ttk.Scrollbar(
            canvas_frame, orient="horizontal", command=self.canvas.xview
        )
        yscroll = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(
            xscrollcommand=xscroll.set, yscrollcommand=yscroll.set
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        xscroll.grid(row=1, column=0, sticky="ew")
        yscroll.grid(row=0, column=1, sticky="ns")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas.bind("<ButtonPress-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<ButtonPress-2>", self._pan_start)
        self.canvas.bind("<B2-Motion>", self._pan_move)
        self.canvas.bind("<MouseWheel>", self._mouse_wheel)

        details = ttk.Frame(upper, padding=(10, 0, 0, 0), width=330)
        upper.add(details, weight=1)
        ttk.Label(details, text="Point review", font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        self.preview = ttk.Label(
            details, text="Selected point crop preview", anchor="center"
        )
        self.preview.pack(fill="x", pady=(6, 8))
        ttk.Label(
            details,
            textvariable=self.selected_reason,
            wraplength=320,
            justify="left",
        ).pack(fill="x", pady=(0, 8))

        form = ttk.Frame(details)
        form.pack(fill="x")
        ttk.Label(form, text="Elevation (m)").grid(row=0, column=0, sticky="w")
        self.elevation_entry = ttk.Entry(form)
        self.elevation_entry.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(form, text="Classification").grid(row=2, column=0, sticky="w")
        self.type_combo = ttk.Combobox(
            form,
            state="readonly",
            values=tuple(sorted(C.POINT_TYPES)),
        )
        self.type_combo.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        form.columnconfigure(0, weight=1)

        actions = ttk.Frame(details)
        actions.pack(fill="x", pady=4)
        for label, command in (
            ("Apply edit", self.edit_selected),
            ("Approve (A)", self.approve_selected),
            ("Reject (R)", self.reject_selected),
            ("Review required", self.review_selected),
            ("Merge duplicate", self.merge_selected),
            ("Use next association", self.use_alternative_selected),
            ("Delete manual", self.delete_selected),
        ):
            ttk.Button(actions, text=label, command=command).pack(
                fill="x", pady=2
            )

        table_frame = ttk.Frame(vertical)
        vertical.add(table_frame, weight=2)
        columns = (
            "id",
            "type",
            "elevation",
            "east",
            "north",
            "status",
            "source",
            "confidence",
        )
        self.table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "id": "Point",
            "type": "Classification",
            "elevation": "Elevation",
            "east": "Local East",
            "north": "Local North",
            "status": "Review status",
            "source": "Source method",
            "confidence": "Class confidence",
        }
        widths = (85, 155, 90, 110, 110, 155, 100, 100)
        for column, width in zip(columns, widths):
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=width, anchor="w")
        table_scroll = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.table.yview
        )
        self.table.configure(yscrollcommand=table_scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        table_scroll.pack(side="right", fill="y")
        self.table.bind("<<TreeviewSelect>>", lambda _event: self._show_selected())

    def _bind_shortcuts(self) -> None:
        self.root.bind("<KeyPress-a>", lambda _event: self.approve_selected())
        self.root.bind("<KeyPress-r>", lambda _event: self.reject_selected())
        self.root.bind("<KeyPress-e>", lambda _event: self._classify_shortcut(C.EXISTING_GROUND))
        self.root.bind("<KeyPress-d>", lambda _event: self._classify_shortcut(C.DESIGN_GRADE))
        self.root.bind("<KeyPress-m>", lambda _event: self.begin_manual_point())
        self.root.bind("<Delete>", lambda _event: self.delete_selected())
        self.root.bind("<Escape>", lambda _event: self.cancel_tool())
        self.root.bind("<Down>", lambda _event: self._select_adjacent(1))
        self.root.bind("<Up>", lambda _event: self._select_adjacent(-1))

    # -- source / project -------------------------------------------------

    def new_from_source(self) -> None:
        filename = filedialog.askopenfilename(
            title="Open local civil plan PDF or image",
            filetypes=[
                ("Civil plan sources", ("*.pdf", "*.png")),
                ("PDF plans", "*.pdf"),
                ("PNG images", "*.png"),
            ],
        )
        if not filename:
            return
        name = simpledialog.askstring(
            "Project name",
            "Name this local preliminary civil project:",
            initialvalue=Path(filename).stem,
            parent=self.root,
        )
        if not name:
            return
        try:
            selected = Path(filename).resolve()
            if selected.suffix.lower() == ".pdf":
                document = inspect_pdf(selected)
                page_number = simpledialog.askinteger(
                    "PDF page",
                    f"Page to review (1–{document.page_count}):",
                    initialvalue=1,
                    minvalue=1,
                    maxvalue=document.page_count,
                    parent=self.root,
                )
                if page_number is None:
                    return
                self.pdf_page_index = page_number - 1
                cache = self._civil_cache() / document.sha256[:16]
                display_path = render_pdf_page(
                    selected,
                    self.pdf_page_index,
                    cache,
                    dpi=self.render_dpi,
                )
                manifest = document.to_manifest(include_local_path=True)
                manifest["selected_page_index"] = self.pdf_page_index
                manifest["render_dpi"] = self.render_dpi
                source_label = (
                    f"{document.display_name}, page {page_number} "
                    f"of {document.page_count}"
                )
            else:
                source = inspect_png(selected)
                manifest = source.to_manifest(include_local_path=True)
                display_path = selected
                self.pdf_page_index = 0
                source_label = (
                    f"{source.display_name} "
                    f"({source.width_px}×{source.height_px})"
                )
            project = new_project(
                name,
                manifest,
                now=_utc_now,
            )
        except Exception as exc:
            messagebox.showerror("Source rejected", str(exc), parent=self.root)
            return
        self.project = project
        self.workflow = CivilWorkflow(project, now=_utc_now)
        self.project_path = None
        self.source_path = selected
        self.display_source_path = display_path
        self._load_image(display_path)
        if self.original_image is not None:
            project.source_manifest["width_px"] = self.original_image.width()
            project.source_manifest["height_px"] = self.original_image.height()
            project.pages = [
                {
                    "page_index": self.pdf_page_index,
                    "page_label": str(self.pdf_page_index + 1),
                    "width_px": self.original_image.width(),
                    "height_px": self.original_image.height(),
                }
            ]
        self.status.set(
            f"Loaded {source_label}; "
            "select a crop, then calibrate."
        )
        self._refresh()

    def new_from_png(self) -> None:
        """Compatibility alias retained for scripted UI callers."""
        self.new_from_source()

    def open_project(self) -> None:
        filename = filedialog.askopenfilename(
            title="Open Screen2XYZ civil project",
            filetypes=[("Screen2XYZ civil project", "*.s2c.json")],
        )
        if not filename:
            return
        try:
            project = load_project(Path(filename))
        except ProjectPersistenceError as exc:
            messagebox.showerror("Project could not open", str(exc), parent=self.root)
            return
        self.project = project
        self.workflow = CivilWorkflow(project, now=_utc_now)
        self.project_path = Path(filename).resolve()
        local_path = project.source_manifest.get("local_path")
        self.source_path = Path(str(local_path)) if local_path else None
        if self.source_path and self.source_path.is_file():
            try:
                if project.source_manifest.get("source_type") == "PDF":
                    self.pdf_page_index = int(
                        project.source_manifest.get("selected_page_index", 0)
                    )
                    self.render_dpi = int(
                        project.source_manifest.get("render_dpi", 150)
                    )
                    self.display_source_path = render_pdf_page(
                        self.source_path,
                        self.pdf_page_index,
                        self._civil_cache()
                        / str(project.source_manifest.get("sha256", ""))[:16],
                        dpi=self.render_dpi,
                    )
                else:
                    self.display_source_path = self.source_path
                self._load_image(self.display_source_path)
            except PdfAdapterError as exc:
                self.original_image = None
                self.canvas.delete("all")
                messagebox.showwarning(
                    "PDF source unavailable",
                    str(exc),
                    parent=self.root,
                )
        else:
            self.original_image = None
            self.canvas.delete("all")
            messagebox.showwarning(
                "Source image not found",
                "Project state opened, but its local source image is unavailable. "
                "Point data is preserved; relink support is still required.",
                parent=self.root,
            )
        self.status.set(f"Opened {project.name}")
        self._refresh()

    # -- local extraction -------------------------------------------------

    def extract_pdf_candidates(self) -> None:
        if (
            self.project is None
            or self.workflow is None
            or self.source_path is None
            or self.project.source_manifest.get("source_type") != "PDF"
        ):
            messagebox.showinfo(
                "Vector PDF extraction",
                "Open a PDF project to extract its local vector text.",
                parent=self.root,
            )
            return
        try:
            candidates = extract_pdf_text_candidates(
                self.source_path,
                self.pdf_page_index,
                dpi=self.render_dpi,
            )
            shapes = extract_pdf_vector_shapes(
                self.source_path,
                self.pdf_page_index,
                dpi=self.render_dpi,
            )
            symbols = detect_symbols(shapes)
            result = self.workflow.ingest_text_candidates(candidates, symbols)
        except (PdfAdapterError, WorkflowError) as exc:
            messagebox.showerror(
                "PDF extraction failed", str(exc), parent=self.root
            )
            return
        self.status.set(
            f"PDF: {len(candidates)} text boxes and {len(symbols)} symbol "
            f"proposals inspected; "
            f"{len(result['added'])} numeric review candidates added; "
            f"{len(result['filtered'])} filtered."
        )
        self._refresh()

    def run_local_ocr(self) -> None:
        if not self._ready_for_canvas() or self.project is None or self.workflow is None:
            return
        crop = self.project.crop or CropRegion(
            0, 0, self.original_image.width(), self.original_image.height()
        )
        try:
            crop_path = self._write_ocr_crop(crop)
            adapter = WindowsOcrAdapter(self._repository_root())
            result = adapter.extract(crop_path)
            candidates = result.text_candidates(
                page_index=self.pdf_page_index,
                offset_x=crop.x,
                offset_y=crop.y,
            )
            ingestion = self.workflow.ingest_text_candidates(candidates)
        except (OcrAdapterError, WorkflowError, tk.TclError, OSError) as exc:
            messagebox.showerror("Local OCR failed", str(exc), parent=self.root)
            return
        self.status.set(
            f"Local OCR: {len(candidates)} word boxes inspected; "
            f"{len(ingestion['added'])} numeric review candidates added; "
            f"{len(ingestion['filtered'])} filtered."
        )
        self._refresh()

    def _write_ocr_crop(self, crop: CropRegion) -> Path:
        if self.original_image is None or self.project is None:
            raise OcrAdapterError("source image is unavailable")
        x1, y1 = int(crop.x), int(crop.y)
        x2, y2 = int(crop.x + crop.width), int(crop.y + crop.height)
        image = tk.PhotoImage(width=x2 - x1, height=y2 - y1, master=self.root)
        image.tk.call(
            str(image),
            "copy",
            str(self.original_image),
            "-from",
            x1,
            y1,
            x2,
            y2,
        )
        target = self._civil_cache() / self.project.project_id / "selected-crop.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        image.write(str(target), format="png")
        return target

    def save_project(self, *, save_as: bool = False) -> None:
        if self.project is None:
            self._need_project()
            return
        path = None if save_as else self.project_path
        if path is None:
            filename = filedialog.asksaveasfilename(
                title="Save Screen2XYZ civil project",
                defaultextension=".s2c.json",
                filetypes=[("Screen2XYZ civil project", "*.s2c.json")],
                initialfile=f"{self.project.name}.s2c.json",
            )
            if not filename:
                return
            path = Path(filename)
        try:
            identity = save_project(self.project, path)
        except ProjectPersistenceError as exc:
            messagebox.showerror("Project save failed", str(exc), parent=self.root)
            return
        self.project_path = Path(identity["path"])
        self.status.set(
            f"Saved {self.project_path.name} (sha256 {identity['sha256'][:12]}…)"
        )

    # -- canvas tools -----------------------------------------------------

    def begin_crop(self) -> None:
        if not self._ready_for_canvas():
            return
        self._tool = "crop"
        self.status.set("Crop tool: drag a rectangle around the working plan region.")

    def begin_calibration(self) -> None:
        if not self._ready_for_canvas():
            return
        known = simpledialog.askfloat(
            "Known scale distance",
            "Known distance between the first two clicks (metres):",
            minvalue=0.000001,
            parent=self.root,
        )
        if known is None:
            return
        east = simpledialog.askfloat(
            "Local origin Easting",
            "Local Easting at the origin click (metres):",
            initialvalue=0.0,
            parent=self.root,
        )
        north = simpledialog.askfloat(
            "Local origin Northing",
            "Local Northing at the origin click (metres):",
            initialvalue=0.0,
            parent=self.root,
        )
        if east is None or north is None:
            return

        def apply(points: list[PixelPoint]) -> None:
            assert self.workflow is not None
            try:
                calibration = self.workflow.apply_calibration(
                    scale_point_1=points[0],
                    scale_point_2=points[1],
                    known_distance_m=known,
                    origin_pixel=points[2],
                    east_reference=points[3],
                    origin_east_m=east,
                    origin_north_m=north,
                )
            except (WorkflowError, ValueError) as exc:
                messagebox.showerror("Calibration rejected", str(exc), parent=self.root)
                return
            self.status.set(
                f"Calibration revision {calibration.revision}: "
                f"{calibration.metres_per_pixel:.9f} m/px. "
                "Run the optional second-distance check."
            )
            self._refresh()

        self._begin_collect(
            4,
            apply,
            "Click scale point 1, scale point 2, local origin, then a point on +East.",
        )

    def begin_scale_check(self) -> None:
        if self.project is None or self.project.calibration is None:
            messagebox.showinfo(
                "Scale check", "Calibrate the project first.", parent=self.root
            )
            return
        known = simpledialog.askfloat(
            "Second known distance",
            "Known distance between the two verification clicks (metres):",
            minvalue=0.000001,
            parent=self.root,
        )
        if known is None:
            return

        def verify(points: list[PixelPoint]) -> None:
            assert self.workflow is not None
            try:
                result = self.workflow.verify_current_scale(
                    points[0], points[1], known
                )
            except WorkflowError as exc:
                messagebox.showerror("Scale check failed", str(exc), parent=self.root)
                return
            title = "Scale check passed" if result.passed else "Scale check warning"
            messagebox.showinfo(
                title,
                f"Measured {result.measured_distance_m:.4f} m; "
                f"error {result.error_percent:.3f}% "
                f"(threshold {result.warning_threshold_percent:.3f}%).",
                parent=self.root,
            )
            self._refresh()

        self._begin_collect(2, verify, "Click the endpoints of the second known distance.")

    def begin_manual_point(self) -> None:
        if not self._ready_for_canvas():
            return
        value = simpledialog.askstring(
            "Manual point type",
            "E = Existing, D = Design, C = Contour:",
            initialvalue="E",
            parent=self.root,
        )
        if value is None:
            return
        try:
            point_type = manual_type(value)
        except ValueError as exc:
            messagebox.showerror("Invalid point type", str(exc), parent=self.root)
            return
        elevation = simpledialog.askfloat(
            "Point elevation",
            "Elevation in metres:",
            parent=self.root,
        )
        if elevation is None:
            return
        self._manual_payload = (elevation, point_type)

        def add(points: list[PixelPoint]) -> None:
            assert self.workflow is not None
            assert self._manual_payload is not None
            try:
                point = self.workflow.add_manual_point(
                    pixel=points[0],
                    elevation=self._manual_payload[0],
                    point_type=self._manual_payload[1],
                )
            except WorkflowError as exc:
                messagebox.showerror("Point rejected", str(exc), parent=self.root)
                return
            self.status.set(
                f"Added {point.id}; review and explicitly approve or reject it."
            )
            self._refresh(select_id=point.id)

        self._begin_collect(1, add, "Click the exact point marker location.")

    def begin_move_point(self) -> None:
        point = self._selected_point()
        if point is None or not self._ready_for_canvas():
            return

        def move(points: list[PixelPoint]) -> None:
            assert self.workflow is not None
            try:
                self.workflow.edit_point(point.id, pixel=points[0])
            except WorkflowError as exc:
                messagebox.showerror("Move rejected", str(exc), parent=self.root)
                return
            self.status.set(f"Moved {point.id}; approval is required again.")
            self._refresh(select_id=point.id)

        self._begin_collect(1, move, f"Click the new marker location for {point.id}.")

    def begin_geometry(self, kind: str) -> None:
        if not self._ready_for_canvas() or self.workflow is None:
            return
        minimum = 3 if kind in {"boundary", "exclusion"} else 2
        count = simpledialog.askinteger(
            "Geometry vertices",
            f"Number of reviewed {kind.replace('_', '-')} vertices:",
            initialvalue=4 if minimum == 3 else 2,
            minvalue=minimum,
            maxvalue=100,
            parent=self.root,
        )
        if count is None:
            return

        def apply(points: list[PixelPoint]) -> None:
            assert self.workflow is not None
            try:
                if kind == "boundary":
                    self.workflow.set_boundary(points)
                elif kind == "exclusion":
                    self.workflow.add_exclusion_polygon(points)
                elif kind == "breakline":
                    self.workflow.add_breakline(points)
                else:
                    self.workflow.add_no_cross_line(points)
            except WorkflowError as exc:
                messagebox.showerror("Geometry rejected", str(exc), parent=self.root)
                return
            self.status.set(
                f"Stored reviewed {kind.replace('_', '-')} with {len(points)} vertices."
            )
            self._refresh()

        self._begin_collect(
            count,
            apply,
            f"Click {count} reviewed vertices for the {kind.replace('_', '-')} in order.",
        )

    def _begin_collect(
        self,
        count: int,
        callback: Callable[[list[PixelPoint]], None],
        instruction: str,
    ) -> None:
        self._tool = "collect"
        self._collector = []
        self._collect_count = count
        self._collect_callback = callback
        self.status.set(instruction)

    def cancel_tool(self) -> None:
        self._tool = "select"
        self._collector = []
        self._collect_callback = None
        if self._drag_rect is not None:
            self.canvas.delete(self._drag_rect)
            self._drag_rect = None
        self.status.set("Tool cancelled.")

    def _on_left_press(self, event) -> None:
        if self.original_image is None:
            return
        point = self._event_source_point(event)
        if self._tool == "collect":
            self._collector.append(point)
            self._draw_collection_marker(point, len(self._collector))
            if len(self._collector) == self._collect_count:
                callback = self._collect_callback
                points = list(self._collector)
                self._tool = "select"
                self._collector = []
                self._collect_callback = None
                if callback is not None:
                    callback(points)
            else:
                self.status.set(
                    f"Recorded click {len(self._collector)} of {self._collect_count}."
                )
            return
        if self._tool == "crop":
            self._crop_start = point
            if self._drag_rect is not None:
                self.canvas.delete(self._drag_rect)
            x = source_to_canvas(point.x, self.zoom)
            y = source_to_canvas(point.y, self.zoom)
            self._drag_rect = self.canvas.create_rectangle(
                x, y, x, y, outline="#facc15", width=2, dash=(6, 3)
            )

    def _on_left_motion(self, event) -> None:
        if self._tool != "crop" or self._crop_start is None or self._drag_rect is None:
            return
        point = self._event_source_point(event)
        self.canvas.coords(
            self._drag_rect,
            source_to_canvas(self._crop_start.x, self.zoom),
            source_to_canvas(self._crop_start.y, self.zoom),
            source_to_canvas(point.x, self.zoom),
            source_to_canvas(point.y, self.zoom),
        )

    def _on_left_release(self, event) -> None:
        if self._tool != "crop" or self._crop_start is None:
            return
        end = self._event_source_point(event)
        x1, x2 = sorted((self._crop_start.x, end.x))
        y1, y2 = sorted((self._crop_start.y, end.y))
        self._crop_start = None
        self._tool = "select"
        if x2 - x1 < 2 or y2 - y1 < 2:
            self.status.set("Crop was too small; no change applied.")
            self._refresh()
            return
        assert self.workflow is not None
        try:
            self.workflow.set_crop(CropRegion(x1, y1, x2 - x1, y2 - y1))
        except WorkflowError as exc:
            messagebox.showerror("Crop rejected", str(exc), parent=self.root)
            return
        self.status.set(
            f"Crop set: x {x1:.1f}, y {y1:.1f}, "
            f"{x2 - x1:.1f}×{y2 - y1:.1f} px."
        )
        self._refresh()

    # -- review actions ---------------------------------------------------

    def edit_selected(self) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        try:
            elevation = float(self.elevation_entry.get().strip())
            point_type = self.type_combo.get()
            self.workflow.edit_point(
                point.id, elevation=elevation, point_type=point_type
            )
        except (ValueError, WorkflowError) as exc:
            messagebox.showerror("Edit rejected", str(exc), parent=self.root)
            return
        self.status.set(f"Edited {point.id}; explicit approval is required again.")
        self._refresh(select_id=point.id)

    def approve_selected(self) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        try:
            self.workflow.approve_point(point.id)
        except WorkflowError as exc:
            messagebox.showerror("Approval blocked", str(exc), parent=self.root)
            return
        self.status.set(f"Approved {point.id}.")
        self._refresh(select_id=point.id)

    def reject_selected(self) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        self.workflow.reject_point(point.id)
        self.status.set(f"Rejected {point.id}; it will not export.")
        self._refresh(select_id=point.id)

    def review_selected(self) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        reason = simpledialog.askstring(
            "Review required",
            "Reason this point needs further review:",
            initialvalue="Association or classification requires review.",
            parent=self.root,
        )
        if not reason:
            return
        self.workflow.mark_review_required(point.id, reason)
        self._refresh(select_id=point.id)

    def merge_selected(self) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        duplicate_id = simpledialog.askstring(
            "Merge duplicate",
            f"Point ID to reject as a duplicate of {point.id}:",
            parent=self.root,
        )
        if not duplicate_id:
            return
        try:
            self.workflow.merge_duplicate(point.id, duplicate_id.strip())
        except WorkflowError as exc:
            messagebox.showerror("Merge blocked", str(exc), parent=self.root)
            return
        self.status.set(f"Merged {duplicate_id.strip()} into {point.id}.")
        self._refresh(select_id=point.id)

    def delete_selected(self) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        if not messagebox.askyesno(
            "Delete manual point",
            f"Delete {point.id}? Only manual points can be deleted.",
            parent=self.root,
        ):
            return
        try:
            self.workflow.delete_manual_point(point.id)
        except WorkflowError as exc:
            messagebox.showerror("Delete blocked", str(exc), parent=self.root)
            return
        self.status.set(f"Deleted manual point {point.id}.")
        self._refresh()

    def use_alternative_selected(self) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        try:
            self.workflow.use_alternative_association(point.id)
        except WorkflowError as exc:
            messagebox.showinfo(
                "No alternative association", str(exc), parent=self.root
            )
            return
        self.status.set(
            f"Applied an alternative association to {point.id}; re-review required."
        )
        self._refresh(select_id=point.id)

    def _classify_shortcut(self, point_type: str) -> None:
        point = self._selected_point()
        if point is None or self.workflow is None:
            return
        try:
            self.workflow.edit_point(point.id, point_type=point_type)
        except WorkflowError as exc:
            messagebox.showerror("Classification blocked", str(exc), parent=self.root)
            return
        self._refresh(select_id=point.id)

    # -- QA / export ------------------------------------------------------

    def show_qa(self) -> None:
        if self.project is None:
            self._need_project()
            return
        summary = qa_summary(self.project)
        counts = summary["issue_counts"]
        messagebox.showinfo(
            "Civil project QA",
            (
                f"Existing approved: {summary['existing_approved']} / "
                f"{summary['existing_candidates']}\n"
                f"Design approved: {summary['design_approved']} / "
                f"{summary['design_candidates']}\n"
                f"Review required: {summary['review_required']}\n"
                f"Rejected: {summary['rejected']}\n"
                f"Duplicates: {summary['duplicate_candidates']} "
                f"(conflicts {summary['conflicting_elevations']})\n"
                f"Issues — critical {counts['CRITICAL']}, error {counts['ERROR']}, "
                f"warning {counts['WARNING']}, info {counts['INFO']}"
            ),
            parent=self.root,
        )

    def show_surface(self, point_type: str) -> None:
        if self.project is None or self.workflow is None:
            self._need_project()
            return
        if not self.project.feature_flags.get("preliminary_surface", False):
            if not messagebox.askyesno(
                "Enable PRELIMINARY surface preview",
                (
                    f"{PRELIMINARY_WARNING}\n\n"
                    "The TIN is an estimator preview only. It does not infer "
                    "engineering breaklines. Enable it for this project?"
                ),
                parent=self.root,
            ):
                return
            self.project.feature_flags["preliminary_surface"] = True
        try:
            surface = build_project_surface(self.project, point_type)
        except SurfaceError as exc:
            messagebox.showerror("Surface preview blocked", str(exc), parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"PRELIMINARY {point_type} TIN")
        dialog.geometry("900x680")
        tk.Label(
            dialog,
            text=f"PRELIMINARY — {PRELIMINARY_WARNING}",
            bg="#7f1d1d",
            fg="white",
            padx=8,
            pady=6,
        ).pack(fill="x")
        info = ttk.Label(
            dialog,
            text=(
                f"{len(surface.vertices)} reviewed vertices; "
                f"{sum(not item.disabled for item in surface.triangles)} active "
                f"of {len(surface.triangles)} triangles. "
                "Click a triangle to disable it."
            ),
        )
        info.pack(fill="x", padx=8, pady=6)
        canvas = tk.Canvas(dialog, bg="#111827", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        vertices = surface.vertex_map()
        xs = [vertex.east for vertex in surface.vertices]
        ys = [vertex.north for vertex in surface.vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1e-9)
        span_y = max(max_y - min_y, 1e-9)

        def mapped(vertex):
            width = max(canvas.winfo_width(), 700) - 60
            height = max(canvas.winfo_height(), 500) - 60
            return (
                30 + (vertex.east - min_x) / span_x * width,
                30 + (max_y - vertex.north) / span_y * height,
            )

        def disable(triangle_id: str) -> None:
            if not messagebox.askyesno(
                "Disable triangle",
                f"Disable {triangle_id} in this preliminary project surface?",
                parent=dialog,
            ):
                return
            try:
                self.workflow.disable_triangle(triangle_id)
            except WorkflowError as exc:
                messagebox.showerror("Disable failed", str(exc), parent=dialog)
                return
            dialog.destroy()
            self.show_surface(point_type)

        def draw() -> None:
            canvas.delete("all")
            for triangle in surface.triangles:
                coordinates = []
                for vertex_id in triangle.vertex_ids:
                    coordinates.extend(mapped(vertices[vertex_id]))
                color = (
                    "#ef4444"
                    if "LONG_TRIANGLE" in triangle.flags
                    else "#f59e0b"
                    if "STEEP_TRIANGLE" in triangle.flags
                    else "#60a5fa"
                )
                item = canvas.create_polygon(
                    coordinates,
                    fill="" if not triangle.disabled else "#374151",
                    outline=color,
                    width=2,
                    dash=(4, 3) if triangle.disabled else (),
                )
                canvas.tag_bind(
                    item,
                    "<Button-1>",
                    lambda _event, triangle_id=triangle.id: disable(triangle_id),
                )
                center_x = sum(coordinates[0::2]) / 3
                center_y = sum(coordinates[1::2]) / 3
                canvas.create_text(
                    center_x,
                    center_y,
                    text=triangle.id,
                    fill="#e5e7eb",
                )
            for vertex in surface.vertices:
                x, y = mapped(vertex)
                canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="white")
                canvas.create_text(
                    x + 5,
                    y - 5,
                    text=f"{vertex.id} z={vertex.elevation:.2f}",
                    fill="white",
                    anchor="sw",
                )

        canvas.bind("<Configure>", lambda _event: draw())
        dialog.after(50, draw)

    def show_cut_fill(self) -> None:
        if self.project is None:
            self._need_project()
            return
        try:
            result = cut_fill_preview(
                build_project_surface(self.project, C.EXISTING_GROUND),
                build_project_surface(self.project, C.DESIGN_GRADE),
            )
        except SurfaceError as exc:
            messagebox.showerror("Cut/fill preview blocked", str(exc), parent=self.root)
            return
        messagebox.showinfo(
            "PRELIMINARY cut/fill point samples",
            (
                f"Overlapping Design-vertex samples: {result['sample_count']}\n"
                f"Fill samples: {result['fill_sample_count']}\n"
                f"Cut samples: {result['cut_sample_count']}\n"
                f"Mean Design − Existing: "
                f"{result['mean_design_minus_existing_m']:.4f} m\n\n"
                "This is not a volume calculation."
            ),
            parent=self.root,
        )

    def enable_landxml(self) -> None:
        if self.project is None:
            self._need_project()
            return
        if not self.project.boundaries:
            messagebox.showerror(
                "LandXML gate",
                "Set and review a boundary before enabling preliminary LandXML.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Accept preliminary triangulation",
            (
                f"{PRELIMINARY_WARNING}\n\n"
                "I have reviewed the points, boundary, exclusions, and "
                "preliminary triangulation. Enable gated LandXML export?"
            ),
            parent=self.root,
        ):
            return
        self.project.feature_flags["landxml"] = True
        self.project.exports_stale = True
        self.status.set("Preliminary LandXML gate accepted for the next export.")

    def export_reviewed(self) -> None:
        if self.project is None:
            self._need_project()
            return
        folder = filedialog.askdirectory(
            title="Choose folder for versioned civil handoff package"
        )
        if not folder:
            return
        try:
            result = export_handoff(self.project, Path(folder), now=_utc_now)
        except ExportError as exc:
            messagebox.showerror("Export blocked", str(exc), parent=self.root)
            return
        if self.project_path is not None:
            save_project(self.project, self.project_path)
        self.status.set(
            f"Exported {result['approved_count']} approved points to "
            f"{result['export_dir'].name}."
        )
        messagebox.showinfo(
            "Preliminary handoff created",
            (
                f"Existing: {result['existing_count']}\n"
                f"Design: {result['design_count']}\n"
                f"All approved terrain points: {result['approved_count']}\n\n"
                f"{PRELIMINARY_WARNING}\n\n"
                f"Folder: {result['export_dir']}"
            ),
            parent=self.root,
        )
        self._refresh()

    # -- rendering / selection -------------------------------------------

    def _load_image(self, path: Path) -> None:
        try:
            self.original_image = tk.PhotoImage(file=str(path), master=self.root)
        except tk.TclError as exc:
            messagebox.showerror(
                "Image cannot be displayed",
                f"Tk could not load this PNG: {exc}",
                parent=self.root,
            )
            self.original_image = None
            return
        self.zoom = 1.0
        self._render_image()

    def _render_image(self) -> None:
        self.canvas.delete("all")
        if self.original_image is None:
            return
        operation, factor = zoom_operation(self.zoom)
        self.display_image = (
            self.original_image.zoom(factor)
            if operation == "zoom"
            else self.original_image.subsample(factor)
        )
        self.canvas.create_image(0, 0, image=self.display_image, anchor="nw", tags="source")
        self.canvas.configure(
            scrollregion=(
                0,
                0,
                self.original_image.width() * self.zoom,
                self.original_image.height() * self.zoom,
            )
        )
        self._draw_overlays()

    def _draw_overlays(self) -> None:
        self.canvas.delete("overlay")
        if self.project is None:
            return
        if self.project.crop is not None:
            crop = self.project.crop
            self.canvas.create_rectangle(
                source_to_canvas(crop.x, self.zoom),
                source_to_canvas(crop.y, self.zoom),
                source_to_canvas(crop.x + crop.width, self.zoom),
                source_to_canvas(crop.y + crop.height, self.zoom),
                outline="#facc15",
                width=2,
                dash=(7, 4),
                tags=("overlay",),
            )
        if self.project.calibration is not None:
            calibration = self.project.calibration
            self._marker(calibration.origin_pixel, "#22c55e", "O")
            east_tip = PixelPoint(
                calibration.origin_pixel.x + calibration.east_unit_x * 60,
                calibration.origin_pixel.y - calibration.east_unit_y * 60,
            )
            self.canvas.create_line(
                source_to_canvas(calibration.origin_pixel.x, self.zoom),
                source_to_canvas(calibration.origin_pixel.y, self.zoom),
                source_to_canvas(east_tip.x, self.zoom),
                source_to_canvas(east_tip.y, self.zoom),
                fill="#22c55e",
                width=3,
                arrow="last",
                tags=("overlay",),
            )
            self.canvas.create_text(
                source_to_canvas(east_tip.x, self.zoom) + 8,
                source_to_canvas(east_tip.y, self.zoom),
                text="+E",
                fill="#dcfce7",
                anchor="w",
                tags=("overlay",),
            )
        for point in self.project.points:
            self._draw_point(point)
        for polygon in self.project.boundaries:
            self._draw_polyline(polygon, "#22c55e", closed=True, width=3)
        for polygon in self.project.exclusion_polygons:
            self._draw_polyline(polygon, "#ef4444", closed=True, width=2)
        for line in self.project.breaklines:
            self._draw_polyline(line, "#22d3ee", closed=False, width=3)
        for line in self.project.no_cross_lines:
            self._draw_polyline(line, "#f472b6", closed=False, width=3)

    def _draw_polyline(
        self,
        points: list[PixelPoint],
        color: str,
        *,
        closed: bool,
        width: int,
    ) -> None:
        if len(points) < 2:
            return
        values = []
        for point in points:
            values.extend(
                (
                    source_to_canvas(point.x, self.zoom),
                    source_to_canvas(point.y, self.zoom),
                )
            )
        if closed:
            values.extend(values[:2])
        self.canvas.create_line(
            *values, fill=color, width=width, tags=("overlay",)
        )

    def _draw_point(self, point: CivilPoint) -> None:
        x = source_to_canvas(point.pixel_x, self.zoom)
        y = source_to_canvas(point.pixel_y, self.zoom)
        radius = max(4, 6 * min(self.zoom, 2))
        color = point_color(point.point_type, point.review_status)
        tags = ("overlay", f"point:{point.id}")
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline="white",
            fill=color,
            width=2,
            tags=tags,
        )
        self.canvas.create_text(
            x + radius + 3,
            y - radius,
            text=f"{point.id} {point.elevation:.2f}",
            fill="white",
            anchor="sw",
            tags=tags,
        )
        self.canvas.tag_bind(
            f"point:{point.id}",
            "<Button-1>",
            lambda _event, point_id=point.id: self._select_point(point_id),
        )
        if point.text_bbox:
            bbox = point.text_bbox
            self.canvas.create_rectangle(
                source_to_canvas(float(bbox["x0"]), self.zoom),
                source_to_canvas(float(bbox["y0"]), self.zoom),
                source_to_canvas(float(bbox["x1"]), self.zoom),
                source_to_canvas(float(bbox["y1"]), self.zoom),
                outline="#38bdf8",
                dash=(3, 2),
                tags=tags,
            )

    def _marker(self, point: PixelPoint, color: str, label: str) -> None:
        x = source_to_canvas(point.x, self.zoom)
        y = source_to_canvas(point.y, self.zoom)
        self.canvas.create_line(
            x - 7, y, x + 7, y, fill=color, width=2, tags=("overlay",)
        )
        self.canvas.create_line(
            x, y - 7, x, y + 7, fill=color, width=2, tags=("overlay",)
        )
        self.canvas.create_text(
            x + 9, y - 9, text=label, fill=color, anchor="sw", tags=("overlay",)
        )

    def _draw_collection_marker(self, point: PixelPoint, index: int) -> None:
        x = source_to_canvas(point.x, self.zoom)
        y = source_to_canvas(point.y, self.zoom)
        self.canvas.create_oval(
            x - 5,
            y - 5,
            x + 5,
            y + 5,
            outline="#f472b6",
            width=2,
            tags=("overlay",),
        )
        self.canvas.create_text(
            x + 8,
            y,
            text=str(index),
            fill="#fce7f3",
            anchor="w",
            tags=("overlay",),
        )

    def _refresh(self, *, select_id: str | None = None) -> None:
        self._refresh_table()
        self._draw_overlays()
        if self.project and self.project.calibration:
            calibration = self.project.calibration
            check = ""
            if calibration.scale_check is not None:
                check = (
                    f"; check {'PASS' if calibration.scale_check.passed else 'WARN'} "
                    f"{calibration.scale_check.error_percent:.2f}%"
                )
            self.calibration_status.set(
                f"Calibration r{calibration.revision}: "
                f"{calibration.metres_per_pixel:.8f} m/px{check}"
            )
        else:
            self.calibration_status.set("Calibration: not set")
        if select_id:
            self._select_point(select_id)

    def _refresh_table(self) -> None:
        current = set(self.table.get_children())
        wanted: set[str] = set()
        if self.project is not None:
            for point in self.project.points:
                wanted.add(point.id)
                values = (
                    point.id,
                    point.point_type,
                    f"{point.elevation:.6f}",
                    "" if point.local_east is None else f"{point.local_east:.6f}",
                    "" if point.local_north is None else f"{point.local_north:.6f}",
                    point.review_status,
                    point.source_method,
                    (
                        ""
                        if point.classification_confidence is None
                        else f"{point.classification_confidence:.2f}"
                    ),
                )
                if point.id in current:
                    self.table.item(point.id, values=values)
                else:
                    self.table.insert("", "end", iid=point.id, values=values)
        for stale in current - wanted:
            self.table.delete(stale)

    def _show_selected(self) -> None:
        point = self._selected_point()
        if point is None:
            return
        self.elevation_entry.delete(0, "end")
        self.elevation_entry.insert(0, format(point.elevation, ".12g"))
        self.type_combo.set(point.point_type)
        reasons = "; ".join(point.classification_reason) or "No reason recorded."
        confidence = (
            f"text={point.text_confidence}, symbol={point.symbol_confidence}, "
            f"association={point.association_confidence}, "
            f"classification={point.classification_confidence}"
        )
        alternatives = (
            f" Alternatives: {len(point.alternative_associations)}."
            if point.alternative_associations
            else ""
        )
        self.selected_reason.set(
            f"{point.id} — {point.review_status}\n{reasons}\n{confidence}.{alternatives}"
        )
        self._update_crop_preview(point)

    def _update_crop_preview(self, point: CivilPoint) -> None:
        if self.original_image is None:
            self.preview.configure(image="", text="Source image unavailable")
            return
        half = 45
        x1 = max(0, int(point.pixel_x) - half)
        y1 = max(0, int(point.pixel_y) - half)
        x2 = min(self.original_image.width(), int(point.pixel_x) + half)
        y2 = min(self.original_image.height(), int(point.pixel_y) + half)
        try:
            crop = tk.PhotoImage(width=x2 - x1, height=y2 - y1, master=self.root)
            crop.tk.call(
                str(crop),
                "copy",
                str(self.original_image),
                "-from",
                x1,
                y1,
                x2,
                y2,
            )
            self.preview_image = crop.zoom(2)
            self.preview.configure(image=self.preview_image, text="")
        except tk.TclError:
            self.preview.configure(image="", text="Crop preview unavailable")

    def _selected_point(self) -> CivilPoint | None:
        if self.project is None:
            return None
        selected = self.table.selection()
        if not selected:
            return None
        try:
            return self.project.point(selected[0])
        except ValueError:
            return None

    def _select_point(self, point_id: str) -> None:
        if not self.table.exists(point_id):
            return
        self.table.selection_set(point_id)
        self.table.focus(point_id)
        self.table.see(point_id)
        self._show_selected()

    def _select_adjacent(self, direction: int) -> None:
        items = list(self.table.get_children())
        if not items:
            return
        selected = self.table.selection()
        index = items.index(selected[0]) if selected and selected[0] in items else 0
        index = max(0, min(len(items) - 1, index + direction))
        self._select_point(items[index])

    # -- zoom / pan / helpers --------------------------------------------

    def change_zoom(self, direction: int) -> None:
        if self.original_image is None:
            return
        self.zoom = next_zoom(self.zoom, direction)
        self._render_image()
        self.status.set(f"Zoom: {self.zoom * 100:.0f}%")

    def reset_zoom(self) -> None:
        if self.original_image is None:
            return
        self.zoom = 1.0
        self._render_image()

    def _pan_start(self, event) -> None:
        self.canvas.scan_mark(event.x, event.y)

    def _pan_move(self, event) -> None:
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _mouse_wheel(self, event) -> None:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _event_source_point(self, event) -> PixelPoint:
        x = canvas_to_source(self.canvas.canvasx(event.x), self.zoom)
        y = canvas_to_source(self.canvas.canvasy(event.y), self.zoom)
        if self.original_image is not None:
            x = max(0.0, min(float(self.original_image.width()), x))
            y = max(0.0, min(float(self.original_image.height()), y))
        return PixelPoint(x, y)

    def _ready_for_canvas(self) -> bool:
        if self.project is None or self.workflow is None or self.original_image is None:
            self._need_project()
            return False
        return True

    def _need_project(self) -> None:
        messagebox.showinfo(
            "Civil project required",
            "Open a local PNG or an existing .s2c.json project first.",
            parent=self.root,
        )

    def _repository_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _civil_cache(self) -> Path:
        return self._repository_root() / ".lab_work" / "civil_cache"

    def _show_help(self) -> None:
        messagebox.showinfo(
            "Civil Plan Digitizer workflow",
            (
                "1. Open a local PDF/PNG and select the plan crop.\n"
                "2. Calibrate with two scale clicks, an origin, and +East.\n"
                "3. Verify a second known distance.\n"
                "4. Add manual points or extract PDF/OCR candidates.\n"
                "5. Review type, value, marker, and alternatives; approve.\n"
                "6. Optionally review surface constraints/TIN separately.\n"
                "7. Save, inspect QA, then export a versioned handoff.\n\n"
                "Middle-drag pans. Zoom buttons preserve source coordinates. "
                "A/R approve/reject; E/D classify; M adds a manual point.\n\n"
                f"{PRELIMINARY_WARNING}"
            ),
            parent=self.root,
        )

    def run(self) -> None:
        self.root.mainloop()


def launch() -> None:
    CivilPlanDigitizerApp().run()
