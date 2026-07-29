"""Advanced local exports with explicit preliminary/local-coordinate metadata."""

from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
from typing import Iterable

from . import PRELIMINARY_WARNING
from .models import CivilPoint, CivilProject
from .surface import PreliminarySurface
from .transform import to_local


def xyz_bytes(points: Iterable[CivilPoint]) -> bytes:
    return _point_lines(points, order="ENZ")


def nez_bytes(points: Iterable[CivilPoint]) -> bytes:
    return _point_lines(points, order="NEZ")


def geojson_bytes(project: CivilProject, points: Iterable[CivilPoint]) -> bytes:
    features = []
    for point in points:
        features.append(
            {
                "type": "Feature",
                "id": point.id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        point.local_east,
                        point.local_north,
                        point.elevation,
                    ],
                },
                "properties": {
                    "point_type": point.point_type,
                    "description": point.description,
                    "review_status": point.review_status,
                    "source_method": point.source_method,
                    "coordinate_basis": "LOCAL_EAST_NORTH_METRES_NOT_GEODETIC",
                    "preliminary": True,
                },
            }
        )
    value = {
        "type": "FeatureCollection",
        "name": project.name,
        "screen2xyz_warning": PRELIMINARY_WARNING,
        "coordinate_basis": "LOCAL_EAST_NORTH_METRES_NOT_GEODETIC",
        "features": features,
    }
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def dxf_bytes(project: CivilProject, points: Iterable[CivilPoint]) -> bytes:
    lines = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "999",
        PRELIMINARY_WARNING,
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]
    for point in points:
        layer = "S2XYZ_EXISTING" if point.point_type == "EXISTING_GROUND" else "S2XYZ_DESIGN"
        lines.extend(
            [
                "0",
                "POINT",
                "8",
                layer,
                "10",
                _number(point.local_east),
                "20",
                _number(point.local_north),
                "30",
                _number(point.elevation),
                "1000",
                point.id,
            ]
        )
    if project.calibration is not None:
        for index, breakline in enumerate(project.breaklines, start=1):
            local = [to_local(point, project.calibration) for point in breakline]
            lines.extend(["0", "POLYLINE", "8", "S2XYZ_BREAKLINE", "66", "1", "70", "0"])
            for east, north in local:
                lines.extend(
                    [
                        "0",
                        "VERTEX",
                        "8",
                        "S2XYZ_BREAKLINE",
                        "10",
                        _number(east),
                        "20",
                        _number(north),
                        "30",
                        "0.000000",
                    ]
                )
            lines.extend(["0", "SEQEND", "8", "S2XYZ_BREAKLINE", "1000", f"BL-{index:03d}"])
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    return ("\r\n".join(lines) + "\r\n").encode("ascii", errors="replace")


def breaklines_geojson_bytes(project: CivilProject) -> bytes:
    features = []
    if project.calibration is not None:
        for index, line in enumerate(project.breaklines, start=1):
            features.append(
                {
                    "type": "Feature",
                    "id": f"BL-{index:03d}",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            list(to_local(point, project.calibration))
                            for point in line
                        ],
                    },
                    "properties": {
                        "reviewed": True,
                        "preliminary": True,
                        "inferred": False,
                    },
                }
            )
    value = {
        "type": "FeatureCollection",
        "screen2xyz_warning": PRELIMINARY_WARNING,
        "coordinate_basis": "LOCAL_EAST_NORTH_METRES_NOT_GEODETIC",
        "features": features,
    }
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def landxml_bytes(
    project: CivilProject,
    surfaces: Iterable[PreliminarySurface],
) -> bytes:
    if not project.feature_flags.get("landxml", False):
        raise ValueError("LandXML requires explicit preliminary-surface acceptance")
    if not project.boundaries:
        raise ValueError("LandXML requires a reviewed boundary")
    root = ET.Element(
        "LandXML",
        {
            "xmlns": "http://www.landxml.org/schema/LandXML-1.2",
            "version": "1.2",
            "language": "English",
            "readOnly": "true",
        },
    )
    ET.SubElement(
        root,
        "Project",
        {
            "name": project.name,
            "desc": "Screen2XYZ PDF/image-derived PRELIMINARY local surface",
        },
    )
    feature = ET.SubElement(root, "Feature", {"code": "SCREEN2XYZ_PRELIMINARY"})
    ET.SubElement(
        feature,
        "Property",
        {"label": "warning", "value": PRELIMINARY_WARNING},
    )
    surfaces_element = ET.SubElement(root, "Surfaces")
    for surface in surfaces:
        surface_element = ET.SubElement(
            surfaces_element,
            "Surface",
            {
                "name": f"{surface.point_type} PDF-Derived PRELIMINARY",
                "desc": "Local coordinates; estimator/survey review required",
            },
        )
        definition = ET.SubElement(
            surface_element,
            "Definition",
            {"surfType": "TIN", "elevMax": "", "elevMin": ""},
        )
        points_element = ET.SubElement(definition, "Pnts")
        point_numbers = {
            vertex.id: index
            for index, vertex in enumerate(surface.vertices, start=1)
        }
        for vertex in surface.vertices:
            point = ET.SubElement(
                points_element, "P", {"id": str(point_numbers[vertex.id])}
            )
            point.text = (
                f"{_number(vertex.north)} {_number(vertex.east)} "
                f"{_number(vertex.elevation)}"
            )
        faces = ET.SubElement(definition, "Faces")
        for triangle in surface.triangles:
            if triangle.disabled:
                continue
            face = ET.SubElement(faces, "F")
            face.text = " ".join(
                str(point_numbers[vertex_id])
                for vertex_id in triangle.vertex_ids
            )
    buffer = io.BytesIO()
    ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    return buffer.getvalue() + b"\n"


def _point_lines(points: Iterable[CivilPoint], *, order: str) -> bytes:
    lines = []
    for point in points:
        east = _number(point.local_east)
        north = _number(point.local_north)
        elevation = _number(point.elevation)
        values = (
            (east, north, elevation)
            if order == "ENZ"
            else (north, east, elevation)
        )
        lines.append(" ".join(values))
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def _number(value: float | None) -> str:
    if value is None:
        raise ValueError("advanced export point lacks local coordinate")
    return format(float(value), ".6f")
