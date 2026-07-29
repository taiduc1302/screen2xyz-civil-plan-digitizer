"""Feature-flagged, deterministic preliminary TIN surface preview."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from . import PRELIMINARY_WARNING
from . import contracts as C
from .models import CivilProject, PixelPoint
from .transform import to_local


class SurfaceError(RuntimeError):
    """Reviewed inputs cannot form a safe preliminary surface."""


@dataclass(frozen=True)
class SurfaceVertex:
    id: str
    east: float
    north: float
    elevation: float


@dataclass(frozen=True)
class SurfaceTriangle:
    id: str
    vertex_ids: tuple[str, str, str]
    longest_edge_m: float
    max_slope_ratio: float
    flags: tuple[str, ...]
    disabled: bool = False


@dataclass(frozen=True)
class PreliminarySurface:
    point_type: str
    vertices: tuple[SurfaceVertex, ...]
    triangles: tuple[SurfaceTriangle, ...]
    boundary: tuple[tuple[float, float], ...]
    exclusions: tuple[tuple[tuple[float, float], ...], ...]
    breaklines: tuple[tuple[tuple[float, float], ...], ...]
    no_cross_lines: tuple[tuple[tuple[float, float], ...], ...]
    warning: str = PRELIMINARY_WARNING

    def vertex_map(self) -> dict[str, SurfaceVertex]:
        return {vertex.id: vertex for vertex in self.vertices}


def build_project_surface(
    project: CivilProject,
    point_type: str,
    *,
    long_edge_threshold_m: float = 50.0,
    steep_slope_ratio: float = 1.0,
) -> PreliminarySurface:
    if point_type not in {C.EXISTING_GROUND, C.DESIGN_GRADE}:
        raise SurfaceError("surface type must be Existing or Design")
    if project.calibration is None:
        raise SurfaceError("calibration is required for a local surface")
    points = [
        point
        for point in project.points
        if point.point_type == point_type
        and point.approved
        and point.local_east is not None
        and point.local_north is not None
    ]
    if len(points) < 3:
        raise SurfaceError("at least three approved points are required")
    vertices = tuple(
        SurfaceVertex(
            point.id,
            float(point.local_east),
            float(point.local_north),
            point.elevation,
        )
        for point in sorted(points, key=lambda item: item.id)
    )
    boundary = _local_polygon(
        project.boundaries[0] if project.boundaries else [],
        project,
    )
    exclusions = tuple(
        _local_polygon(polygon, project)
        for polygon in project.exclusion_polygons
        if len(polygon) >= 3
    )
    breaklines = tuple(
        _local_polygon(line, project)
        for line in project.breaklines
        if len(line) >= 2
    )
    no_cross_lines = tuple(
        _local_polygon(line, project)
        for line in project.no_cross_lines
        if len(line) >= 2
    )
    triangle_indices = _delaunay(vertices)
    filtered: list[tuple[int, int, int]] = []
    for triangle in triangle_indices:
        triangle_xy = tuple(
            (vertices[index].east, vertices[index].north) for index in triangle
        )
        centroid = (
            sum(point[0] for point in triangle_xy) / 3,
            sum(point[1] for point in triangle_xy) / 3,
        )
        if boundary and (
            not _point_in_polygon(centroid, boundary)
            or _triangle_crosses_polygon(triangle_xy, boundary)
        ):
            continue
        if any(
            _point_in_polygon(centroid, exclusion)
            or _triangle_intersects_polygon(triangle_xy, exclusion)
            for exclusion in exclusions
        ):
            continue
        if any(
            _triangle_crosses_polyline(triangle_xy, line)
            for line in no_cross_lines
        ):
            continue
        if any(
            _triangle_crosses_polyline(triangle_xy, line)
            for line in breaklines
        ):
            continue
        filtered.append(triangle)
    stable = sorted(
        filtered,
        key=lambda triangle: tuple(sorted(vertices[index].id for index in triangle)),
    )
    triangles = []
    for sequence, triangle in enumerate(stable, start=1):
        selected = [vertices[index] for index in triangle]
        edge_lengths = [
            _distance(selected[left], selected[right])
            for left, right in ((0, 1), (1, 2), (2, 0))
        ]
        slopes = [
            _slope(selected[left], selected[right])
            for left, right in ((0, 1), (1, 2), (2, 0))
        ]
        flags: list[str] = []
        if max(edge_lengths) > long_edge_threshold_m:
            flags.append("LONG_TRIANGLE")
        if max(slopes) > steep_slope_ratio:
            flags.append("STEEP_TRIANGLE")
        triangle_id = f"T-{sequence:04d}"
        triangles.append(
            SurfaceTriangle(
                triangle_id,
                tuple(vertex.id for vertex in selected),
                max(edge_lengths),
                max(slopes),
                tuple(flags),
                disabled=triangle_id in project.disabled_triangles,
            )
        )
    return PreliminarySurface(
        point_type=point_type,
        vertices=vertices,
        triangles=tuple(triangles),
        boundary=boundary,
        exclusions=exclusions,
        breaklines=breaklines,
        no_cross_lines=no_cross_lines,
    )


def cut_fill_preview(
    existing: PreliminarySurface, design: PreliminarySurface
) -> dict[str, float | int | str]:
    if existing.point_type != C.EXISTING_GROUND or design.point_type != C.DESIGN_GRADE:
        raise SurfaceError("cut/fill preview requires Existing then Design surfaces")
    samples = []
    for vertex in design.vertices:
        existing_z = _surface_elevation_at(existing, vertex.east, vertex.north)
        if existing_z is not None:
            samples.append(vertex.elevation - existing_z)
    if not samples:
        raise SurfaceError("surfaces do not overlap at any Design vertices")
    return {
        "sample_count": len(samples),
        "fill_sample_count": sum(value > 0 for value in samples),
        "cut_sample_count": sum(value < 0 for value in samples),
        "zero_sample_count": sum(abs(value) <= 1e-12 for value in samples),
        "mean_design_minus_existing_m": sum(samples) / len(samples),
        "minimum_delta_m": min(samples),
        "maximum_delta_m": max(samples),
        "classification": "PRELIMINARY_POINT_SAMPLES_NOT_VOLUME",
    }


def _delaunay(vertices: tuple[SurfaceVertex, ...]) -> list[tuple[int, int, int]]:
    unique_xy = {(vertex.east, vertex.north) for vertex in vertices}
    if len(unique_xy) < 3:
        raise SurfaceError("surface points must contain three unique plan positions")
    min_x = min(vertex.east for vertex in vertices)
    max_x = max(vertex.east for vertex in vertices)
    min_y = min(vertex.north for vertex in vertices)
    max_y = max(vertex.north for vertex in vertices)
    span = max(max_x - min_x, max_y - min_y)
    if span <= 1e-12:
        raise SurfaceError("surface point extent is zero")
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    work = list(vertices) + [
        SurfaceVertex("_SUPER1", center_x - 20 * span, center_y - span, 0),
        SurfaceVertex("_SUPER2", center_x, center_y + 20 * span, 0),
        SurfaceVertex("_SUPER3", center_x + 20 * span, center_y - span, 0),
    ]
    super_indices = (len(vertices), len(vertices) + 1, len(vertices) + 2)
    triangles: list[tuple[int, int, int]] = [super_indices]
    for point_index in range(len(vertices)):
        bad = [
            triangle
            for triangle in triangles
            if _circumcircle_contains(
                work[triangle[0]],
                work[triangle[1]],
                work[triangle[2]],
                work[point_index],
            )
        ]
        edge_counts: dict[tuple[int, int], int] = {}
        for triangle in bad:
            for left, right in (
                (triangle[0], triangle[1]),
                (triangle[1], triangle[2]),
                (triangle[2], triangle[0]),
            ):
                edge = tuple(sorted((left, right)))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        triangles = [triangle for triangle in triangles if triangle not in bad]
        for edge, count in edge_counts.items():
            if count == 1:
                triangles.append((edge[0], edge[1], point_index))
    result = [
        triangle
        for triangle in triangles
        if not any(index in super_indices for index in triangle)
        and abs(_area2(*(work[index] for index in triangle))) > 1e-12
    ]
    if not result:
        raise SurfaceError("surface points are collinear or cannot be triangulated")
    return result


def _circumcircle_contains(
    a: SurfaceVertex,
    b: SurfaceVertex,
    c: SurfaceVertex,
    point: SurfaceVertex,
) -> bool:
    denominator = 2 * (
        a.east * (b.north - c.north)
        + b.east * (c.north - a.north)
        + c.east * (a.north - b.north)
    )
    if abs(denominator) <= 1e-12:
        return False
    a2 = a.east**2 + a.north**2
    b2 = b.east**2 + b.north**2
    c2 = c.east**2 + c.north**2
    center_x = (
        a2 * (b.north - c.north)
        + b2 * (c.north - a.north)
        + c2 * (a.north - b.north)
    ) / denominator
    center_y = (
        a2 * (c.east - b.east)
        + b2 * (a.east - c.east)
        + c2 * (b.east - a.east)
    ) / denominator
    radius_sq = (center_x - a.east) ** 2 + (center_y - a.north) ** 2
    point_sq = (center_x - point.east) ** 2 + (center_y - point.north) ** 2
    return point_sq <= radius_sq + 1e-10


def _local_polygon(
    points: list[PixelPoint], project: CivilProject
) -> tuple[tuple[float, float], ...]:
    if project.calibration is None:
        return ()
    return tuple(to_local(point, project.calibration) for point in points)


def _distance(left: SurfaceVertex, right: SurfaceVertex) -> float:
    return math.hypot(left.east - right.east, left.north - right.north)


def _slope(left: SurfaceVertex, right: SurfaceVertex) -> float:
    distance = _distance(left, right)
    return (
        float("inf")
        if distance <= 1e-12
        else abs(left.elevation - right.elevation) / distance
    )


def _area2(
    a: SurfaceVertex, b: SurfaceVertex, c: SurfaceVertex
) -> float:
    return (
        (b.east - a.east) * (c.north - a.north)
        - (b.north - a.north) * (c.east - a.east)
    )


def _point_in_polygon(
    point: tuple[float, float], polygon: tuple[tuple[float, float], ...]
) -> bool:
    if len(polygon) < 3:
        return False
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if (current[1] > point[1]) != (previous[1] > point[1]):
            crossing_x = (
                (previous[0] - current[0])
                * (point[1] - current[1])
                / (previous[1] - current[1])
                + current[0]
            )
            if point[0] < crossing_x:
                inside = not inside
        previous = current
    return inside


def _triangle_intersects_polygon(
    triangle: tuple[tuple[float, float], ...],
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    if any(_point_in_polygon(vertex, polygon) for vertex in triangle):
        return True
    if any(_point_in_triangle(vertex, triangle) for vertex in polygon):
        return True
    return _triangle_crosses_polygon(triangle, polygon)


def _triangle_crosses_polygon(
    triangle: tuple[tuple[float, float], ...],
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    polygon_edges = list(_segments(polygon, closed=True))
    return any(
        _segments_intersect(left, right, poly_left, poly_right)
        for left, right in _segments(triangle, closed=True)
        for poly_left, poly_right in polygon_edges
    )


def _triangle_crosses_polyline(
    triangle: tuple[tuple[float, float], ...],
    line: tuple[tuple[float, float], ...],
) -> bool:
    return any(
        _segments_intersect(left, right, line_left, line_right)
        for left, right in _segments(triangle, closed=True)
        for line_left, line_right in _segments(line, closed=False)
    )


def _segments(
    points: Iterable[tuple[float, float]], *, closed: bool
) -> Iterable[tuple[tuple[float, float], tuple[float, float]]]:
    values = list(points)
    limit = len(values) if closed else len(values) - 1
    for index in range(max(0, limit)):
        yield values[index], values[(index + 1) % len(values)]


def _segments_intersect(a, b, c, d) -> bool:
    def orientation(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (
            q[1] - p[1]
        ) * (r[0] - p[0])

    values = (orientation(a, b, c), orientation(a, b, d), orientation(c, d, a), orientation(c, d, b))
    # Shared endpoints are legal surface vertices, not crossings.
    if any(_same_point(first, second) for first in (a, b) for second in (c, d)):
        return False
    return values[0] * values[1] < 0 and values[2] * values[3] < 0


def _same_point(left, right) -> bool:
    return abs(left[0] - right[0]) <= 1e-10 and abs(left[1] - right[1]) <= 1e-10


def _point_in_triangle(point, triangle) -> bool:
    a, b, c = triangle
    denominator = (
        (b[1] - c[1]) * (a[0] - c[0])
        + (c[0] - b[0]) * (a[1] - c[1])
    )
    if abs(denominator) <= 1e-12:
        return False
    first = (
        (b[1] - c[1]) * (point[0] - c[0])
        + (c[0] - b[0]) * (point[1] - c[1])
    ) / denominator
    second = (
        (c[1] - a[1]) * (point[0] - c[0])
        + (a[0] - c[0]) * (point[1] - c[1])
    ) / denominator
    third = 1 - first - second
    return first >= -1e-10 and second >= -1e-10 and third >= -1e-10


def _surface_elevation_at(
    surface: PreliminarySurface, east: float, north: float
) -> float | None:
    vertices = surface.vertex_map()
    point = (east, north)
    for triangle in surface.triangles:
        if triangle.disabled:
            continue
        selected = [vertices[vertex_id] for vertex_id in triangle.vertex_ids]
        coordinates = tuple((vertex.east, vertex.north) for vertex in selected)
        if not _point_in_triangle(point, coordinates):
            continue
        a, b, c = coordinates
        denominator = (
            (b[1] - c[1]) * (a[0] - c[0])
            + (c[0] - b[0]) * (a[1] - c[1])
        )
        first = (
            (b[1] - c[1]) * (east - c[0])
            + (c[0] - b[0]) * (north - c[1])
        ) / denominator
        second = (
            (c[1] - a[1]) * (east - c[0])
            + (a[0] - c[0]) * (north - c[1])
        ) / denominator
        third = 1 - first - second
        return (
            first * selected[0].elevation
            + second * selected[1].elevation
            + third * selected[2].elevation
        )
    return None
