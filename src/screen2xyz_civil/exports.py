"""Deterministic approved-only civil and AGTEK handoff exports."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Iterable

from .io_utils import (
    atomic_write_bytes,
    atomic_write_json,
    csv_bytes,
    formula_safe_display,
    sha256_file,
    write_manifest,
)

from . import PRELIMINARY_WARNING
from . import contracts as C
from .advanced_exports import (
    breaklines_geojson_bytes,
    dxf_bytes,
    geojson_bytes,
    landxml_bytes,
)
from .estimator_exports import (
    EstimatorExportError,
    generic_nez_bytes,
    generic_xyz_bytes,
    point_number,
    verify_export_round_trip,
    write_estimator_workbook,
)
from .models import CivilPoint, CivilProject
from .transform import to_local
from .qa import has_critical_export_errors, qa_summary
from .surface import SurfaceError, build_project_surface

AGTEK_HEADER = ("Point", "Northing", "Easting", "Elevation", "Description")
ALL_REVIEWED_HEADER = AGTEK_HEADER + (
    "PointType",
    "ReviewStatus",
    "SourceMethod",
)


class ExportError(RuntimeError):
    """Project cannot be exported without violating review/QA rules."""


def approved_points(project: CivilProject) -> list[CivilPoint]:
    return sorted(
        (
            point
            for point in project.points
            if point.approved
            and point.terrain_relevant
            and point.local_east is not None
            and point.local_north is not None
        ),
        key=lambda point: (point_number(point), point.id),
    )


def export_handoff(
    project: CivilProject,
    output_root: Path,
    *,
    now: Callable[[], str],
    export_id: str | None = None,
    coordinate_order: str = "NE",
    point_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build privately in a staging directory and publish in one rename."""

    timestamp = now()
    token = export_id or re.sub(r"[^0-9A-Za-z]+", "", timestamp)
    if not token:
        raise ExportError("export id is empty after sanitization")
    safe_name = (
        re.sub(r"[^0-9A-Za-z._-]+", "-", project.name).strip("-")
        or "project"
    )
    root = output_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    final_dir = root / f"{safe_name}_export_{token}"
    if final_dir.exists():
        raise ExportError(
            f"versioned export already exists: {final_dir.name}"
        )
    stage_root = root / f".{final_dir.name}.staging-{os.getpid()}"
    if stage_root.exists():
        raise ExportError(
            f"export staging directory already exists: {stage_root.name}"
        )
    history_length = len(project.export_history)
    prior_stale = project.exports_stale
    stage_root.mkdir()
    try:
        result = _build_unpublished_handoff(
            project,
            stage_root,
            now=lambda: timestamp,
            export_id=token,
            coordinate_order=coordinate_order,
            point_ids=point_ids,
        )
        staged_export = Path(result["export_dir"]).resolve()
        if (
            staged_export.parent != stage_root
            or staged_export.name != final_dir.name
        ):
            raise ExportError("export staging path failed containment check")
        os.replace(staged_export, final_dir)
        stage_root.rmdir()
        result["export_dir"] = final_dir
        if "round_trip" in result:
            result["round_trip"]["report_path"] = (
                final_dir / "Export_Round_Trip_Report.md"
            )
        return result
    except Exception:
        del project.export_history[history_length:]
        project.exports_stale = prior_stale
        safe_stage = stage_root.resolve()
        if (
            safe_stage.parent == root
            and safe_stage.name.startswith(f".{final_dir.name}.staging-")
        ):
            shutil.rmtree(safe_stage, ignore_errors=True)
        raise


def _build_unpublished_handoff(
    project: CivilProject,
    output_root: Path,
    *,
    now: Callable[[], str],
    export_id: str | None = None,
    coordinate_order: str = "NE",
    point_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    if coordinate_order not in {"NE", "EN"}:
        raise ExportError("coordinate_order must be NE or EN")
    summary = qa_summary(project)
    if has_critical_export_errors(summary):
        raise ExportError("critical QA errors block export")
    timestamp = now()
    token = export_id or re.sub(r"[^0-9A-Za-z]+", "", timestamp)
    if not token:
        raise ExportError("export id is empty after sanitization")
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "-", project.name).strip("-") or "project"
    export_dir = output_root.expanduser().resolve() / f"{safe_name}_export_{token}"
    if export_dir.exists():
        raise ExportError(f"versioned export already exists: {export_dir.name}")
    export_dir.mkdir(parents=True)

    selected_ids = None if point_ids is None else set(point_ids)
    if selected_ids is not None:
        known_ids = {point.id for point in project.points}
        unknown_ids = selected_ids - known_ids
        if unknown_ids:
            raise ExportError(
                "selected export contains unknown Point Cart IDs: "
                + ", ".join(sorted(unknown_ids))
            )
    points = [
        point
        for point in approved_points(project)
        if selected_ids is None or point.id in selected_ids
    ]
    if selected_ids is not None and not points:
        raise ExportError(
            "none of the selected Point Cart rows are approved terrain points"
        )
    existing = [point for point in points if point.point_type == C.EXISTING_GROUND]
    design = [point for point in points if point.point_type == C.DESIGN_GRADE]
    _write_agtek_csv(export_dir / "Existing_Points.csv", existing, coordinate_order)
    _write_agtek_csv(export_dir / "Design_Points.csv", design, coordinate_order)
    _write_all_reviewed(export_dir / "All_Reviewed_Points.csv", points, coordinate_order)
    atomic_write_bytes(
        export_dir / "Reviewed_Points.xyz", generic_xyz_bytes(points)
    )
    atomic_write_bytes(
        export_dir / "Reviewed_Points.nez", generic_nez_bytes(points)
    )
    try:
        write_estimator_workbook(
            project,
            export_dir / "Approved_Point_Cart.xlsx",
            points,
            qa_summary=summary,
        )
    except EstimatorExportError as exc:
        raise ExportError(f"XLSX export failed: {exc}") from exc
    atomic_write_bytes(
        export_dir / "Reviewed_Points.geojson",
        geojson_bytes(project, points),
    )
    atomic_write_bytes(
        export_dir / "Reviewed_Points.dxf",
        dxf_bytes(project, points),
    )
    atomic_write_bytes(
        export_dir / "Breaklines.geojson",
        breaklines_geojson_bytes(project),
    )
    atomic_write_bytes(
        export_dir / "Contour_Lines.geojson",
        _contour_lines_geojson_bytes(project),
    )
    atomic_write_bytes(
        export_dir / "Contour_Line_Vertices.csv",
        _contour_line_vertices_csv(project),
    )
    atomic_write_json(
        export_dir / "Project_Audit.json",
        _audit_payload(project, summary, timestamp),
    )
    atomic_write_bytes(
        export_dir / "Calibration_Report.md",
        _calibration_report(project).encode("utf-8"),
    )
    atomic_write_bytes(
        export_dir / "QA_Summary.md",
        _qa_report(summary).encode("utf-8"),
    )
    atomic_write_bytes(
        export_dir / "AGTEK_Import_Instructions.md",
        _agtek_instructions(coordinate_order).encode("utf-8"),
    )
    atomic_write_json(
        export_dir / "Source_Manifest.json",
        _redacted_source_manifest(project),
    )
    landxml_status = "NOT_REQUESTED"
    if project.feature_flags.get("landxml", False):
        try:
            surfaces = [
                build_project_surface(project, point_type)
                for point_type in (C.EXISTING_GROUND, C.DESIGN_GRADE)
                if sum(
                    point.approved and point.point_type == point_type
                    for point in project.points
                )
                >= 3
            ]
            if not surfaces:
                raise SurfaceError("no reviewed surface has three approved points")
            atomic_write_bytes(
                export_dir / "Preliminary_Surfaces.xml",
                landxml_bytes(project, surfaces),
            )
            landxml_status = "EXPORTED_PRELIMINARY"
        except (SurfaceError, ValueError) as exc:
            raise ExportError(f"LandXML gate failed: {exc}") from exc
    try:
        round_trip = verify_export_round_trip(
            project,
            export_dir,
            points,
            coordinate_order=coordinate_order,
        )
    except (EstimatorExportError, OSError, ValueError, KeyError) as exc:
        raise ExportError(f"export round-trip verification failed: {exc}") from exc
    if not round_trip["passed"]:
        raise ExportError(
            "export round-trip verification failed; inspect "
            "Export_Round_Trip_Report.md"
        )
    artifact_hashes = {
        path.name: sha256_file(path)
        for path in sorted(export_dir.iterdir(), key=lambda item: item.name)
        if path.is_file()
    }
    handoff_manifest = {
        "schema_version": C.SCHEMA_VERSION,
        "project_id": project.project_id,
        "export_id": token,
        "created_at": timestamp,
        "preliminary": True,
        "warning": PRELIMINARY_WARNING,
        "coordinate_basis": "LOCAL_EAST_NORTH_METRES",
        "coordinate_order": coordinate_order,
        "landxml_status": landxml_status,
        "point_counts": {
            "existing": len(existing),
            "design": len(design),
            "contour": sum(
                point.point_type == C.CONTOUR_ELEVATION for point in points
            ),
            "all_approved": len(points),
        },
        "coordinate_extents": summary["coordinate_extents"],
        "artifact_sha256": artifact_hashes,
    }
    atomic_write_json(export_dir / "Handoff_Manifest.json", handoff_manifest)
    write_manifest(export_dir, export_dir)
    final_hashes = {
        path.name: sha256_file(path)
        for path in sorted(export_dir.iterdir(), key=lambda item: item.name)
        if path.is_file()
    }
    project.export_history.append(
        {
            "export_id": token,
            "created_at": timestamp,
            "folder_name": export_dir.name,
            "calibration_revision": (
                None if project.calibration is None else project.calibration.revision
            ),
            "approved_count": len(points),
            "artifact_sha256": final_hashes,
        }
    )
    project.exports_stale = False
    return {
        "export_dir": export_dir,
        "existing_count": len(existing),
        "design_count": len(design),
        "approved_count": len(points),
        "hashes": final_hashes,
        "qa_summary": summary,
        "round_trip": round_trip,
    }


def _write_agtek_csv(
    path: Path, points: Iterable[CivilPoint], coordinate_order: str
) -> None:
    rows = [_agtek_row(point, coordinate_order) for point in points]
    atomic_write_bytes(path, csv_bytes(rows, AGTEK_HEADER))


def _write_all_reviewed(
    path: Path, points: Iterable[CivilPoint], coordinate_order: str
) -> None:
    rows = []
    for point in points:
        row = _agtek_row(point, coordinate_order)
        row.update(
            {
                "PointType": point.point_type,
                "ReviewStatus": point.review_status,
                "SourceMethod": point.source_method,
            }
        )
        rows.append(row)
    atomic_write_bytes(path, csv_bytes(rows, ALL_REVIEWED_HEADER))


def _agtek_row(point: CivilPoint, coordinate_order: str) -> dict[str, Any]:
    northing = _format_number(point.local_north)
    easting = _format_number(point.local_east)
    if coordinate_order == "EN":
        northing, easting = easting, northing
    return {
        "Point": point_number(point),
        "Northing": northing,
        "Easting": easting,
        "Elevation": _format_number(point.elevation),
        "Description": formula_safe_display(
            point.description or C.DESCRIPTION_BY_TYPE.get(point.point_type, "")
        ),
    }


def _format_number(value: float | None) -> str:
    if value is None:
        return ""
    return format(float(value), ".6f")


def _approved_contour_line_vertices(project: CivilProject) -> list[dict[str, Any]]:
    if project.calibration is None:
        return []
    rows: list[dict[str, Any]] = []
    for line in project.elevation_lines:
        if not line.approved:
            continue
        for index, vertex in enumerate(line.vertices, start=1):
            east, north = to_local(vertex, project.calibration)
            rows.append(
                {
                    "Line": line.id,
                    "Vertex": index,
                    "Northing": _format_number(north),
                    "Easting": _format_number(east),
                    "Elevation": _format_number(line.elevation),
                    "Description": formula_safe_display(line.description),
                    "Sheet": formula_safe_display(line.sheet),
                    "Revision": formula_safe_display(line.revision_label),
                }
            )
    return rows


def _contour_line_vertices_csv(project: CivilProject) -> bytes:
    return csv_bytes(
        _approved_contour_line_vertices(project),
        (
            "Line",
            "Vertex",
            "Northing",
            "Easting",
            "Elevation",
            "Description",
            "Sheet",
            "Revision",
        ),
    )


def _contour_lines_geojson_bytes(project: CivilProject) -> bytes:
    features = []
    if project.calibration is not None:
        for line in project.elevation_lines:
            if not line.approved:
                continue
            coordinates = [
                [*to_local(vertex, project.calibration), line.elevation]
                for vertex in line.vertices
            ]
            features.append(
                {
                    "type": "Feature",
                    "id": line.id,
                    "properties": {
                        "elevation": line.elevation,
                        "description": formula_safe_display(line.description),
                        "sheet": formula_safe_display(line.sheet),
                        "revision": formula_safe_display(line.revision_label),
                        "review_status": line.review_status,
                        "preliminary": True,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates,
                    },
                }
            )
    return (
        json.dumps(
            {
                "type": "FeatureCollection",
                "coordinate_basis": "LOCAL_EAST_NORTH_METRES",
                "warning": PRELIMINARY_WARNING,
                "features": features,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        + b"\n"
    )


def _audit_payload(
    project: CivilProject, summary: dict[str, Any], timestamp: str
) -> dict[str, Any]:
    return {
        "schema_version": C.SCHEMA_VERSION,
        "project_id": project.project_id,
        "project_name": formula_safe_display(project.name),
        "exported_at": timestamp,
        "preliminary": True,
        "warning": PRELIMINARY_WARNING,
        "coordinate_basis": "LOCAL_EAST_NORTH_METRES_NOT_GEODETIC",
        "calibration": (
            None if project.calibration is None else project.calibration.to_dict()
        ),
        "crop": None if project.crop is None else project.crop.to_dict(),
        "qa_summary": summary,
        "points": [point.to_dict() for point in project.points],
        "decision_log": list(project.decision_log),
        "prior_export_history": list(project.export_history),
    }


def _redacted_source_manifest(project: CivilProject) -> dict[str, Any]:
    allowed = {
        "display_name",
        "sha256",
        "byte_size",
        "width_px",
        "height_px",
        "source_type",
        "page_count",
        "sheet_id",
        "revision",
    }
    return {
        "schema_version": C.SCHEMA_VERSION,
        "source": {
            key: value
            for key, value in project.source_manifest.items()
            if key in allowed
        },
        "pages": list(project.pages),
        "local_path_exported": False,
        "warning": PRELIMINARY_WARNING,
    }


def _calibration_report(project: CivilProject) -> str:
    calibration = project.calibration
    if calibration is None:
        return f"# Calibration Report\n\n{PRELIMINARY_WARNING}\n\nNo calibration.\n"
    check = "Not supplied."
    if calibration.scale_check is not None:
        check = (
            f"{calibration.scale_check.measured_distance_m:.6f} m measured "
            f"against {calibration.scale_check.known_distance_m:.6f} m known; "
            f"error {calibration.scale_check.error_percent:.3f}%; "
            f"{'PASS' if calibration.scale_check.passed else 'WARNING'}."
        )
    return (
        "# Calibration Report\n\n"
        f"> {PRELIMINARY_WARNING}\n\n"
        f"- Revision: {calibration.revision}\n"
        f"- Metres per pixel: {calibration.metres_per_pixel:.12f}\n"
        f"- Origin pixel: ({calibration.origin_pixel.x:.6f}, "
        f"{calibration.origin_pixel.y:.6f})\n"
        f"- Local origin: E {calibration.origin_east_m:.6f} m, "
        f"N {calibration.origin_north_m:.6f} m\n"
        f"- East unit in Y-up screen basis: "
        f"({calibration.east_unit_x:.12f}, {calibration.east_unit_y:.12f})\n"
        f"- Second distance check: {check}\n"
        f"- Previous calibration revisions retained: "
        f"{len(project.calibration_history)}\n"
    )


def _qa_report(summary: dict[str, Any]) -> str:
    labels = (
        ("Existing candidates", "existing_candidates"),
        ("Existing approved", "existing_approved"),
        ("Design candidates", "design_candidates"),
        ("Design approved", "design_approved"),
        ("Contour candidates", "contour_candidates"),
        ("Contour approved", "contour_approved"),
        ("Review required", "review_required"),
        ("Rejected", "rejected"),
        ("Duplicate candidates", "duplicate_candidates"),
        ("Conflicting elevations", "conflicting_elevations"),
        ("Out-of-range values", "out_of_range_values"),
        ("Low-confidence OCR", "low_confidence_ocr"),
        ("Unassociated labels", "unassociated_labels"),
        ("Unused symbols", "unused_symbols"),
    )
    lines = ["# QA Summary", "", f"> {PRELIMINARY_WARNING}", ""]
    lines.extend(f"- {label}: {summary[key]}" for label, key in labels)
    lines.extend(["", "## Issues", ""])
    if not summary["issues"]:
        lines.append("No QA issues detected.")
    else:
        lines.extend(
            f"- [{issue['severity']}] {issue['code']}: {issue['detail']}"
            for issue in summary["issues"]
        )
    return "\n".join(lines) + "\n"


def _agtek_instructions(coordinate_order: str) -> str:
    order_note = (
        "Northing, Easting"
        if coordinate_order == "NE"
        else "Easting, Northing values are intentionally mapped into the preset columns"
    )
    return (
        "# AGTEK Import Instructions\n\n"
        f"> {PRELIMINARY_WARNING}\n\n"
        f"Coordinate order in this package: {order_note}. Units are metres in a "
        "local, non-geodetic frame.\n\n"
        "1. Import `Existing_Points.csv` into the Existing Surface.\n"
        "2. Import `Design_Points.csv` into the Design Surface.\n"
        "3. Choose **Do Not Connect Points** or the equivalent option.\n"
        "4. Add real, reviewed breaklines separately.\n"
        "5. Create Existing and Design perimeters separately.\n"
        "6. Inspect each surface in 3D and verify representative elevations.\n"
        "7. Compare point counts and extents with `Handoff_Manifest.json`.\n"
        "8. Do not treat generated data as certified survey information.\n"
    )
