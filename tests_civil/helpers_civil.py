from __future__ import annotations

import struct
import tempfile
import zlib
from pathlib import Path

from screen2xyz_civil import contracts as C
from screen2xyz_civil.models import CropRegion, PixelPoint
from screen2xyz_civil.workflow import CivilWorkflow, new_project

ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = "2026-07-28T21:45:00-07:00"


def clock() -> str:
    return FIXED_NOW


def fresh_dir() -> Path:
    root = ROOT / ".lab_work" / "civil_tests"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="case-", dir=root))


def make_png(path: Path, width: int = 100, height: int = 100) -> Path:
    def chunk(name: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + name
            + data
            + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
        )

    rows = b"".join(b"\x00" + b"\xE8\xEC\xF0" * width for _ in range(height))
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
        )
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(payload)
    return path


def make_vector_pdf(
    path: Path, text: str = "49.06", *, with_shapes: bool = False
) -> Path:
    drawing = ""
    if with_shapes:
        drawing = (
            "100 100 m 110 100 l S "
            "105 95 m 105 105 l S "
            "200 100 m "
            "200 106 205 110 210 110 c "
            "215 110 220 106 220 100 c "
            "220 94 215 90 210 90 c "
            "205 90 200 94 200 100 c h S "
        )
    content = (
        drawing + f"BT /F1 14 Tf 72 720 Td ({text}) Tj ET"
    ).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, value in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode("ascii"))
        data.extend(value)
        data.extend(b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(data)
    return path


def project_and_workflow(*, calibrated: bool = True):
    project = new_project(
        "Synthetic Civil",
        {
            "display_name": "synthetic-plan.png",
            "local_path": "private/local/synthetic-plan.png",
            "sha256": "a" * 64,
            "byte_size": 1234,
            "width_px": 200,
            "height_px": 150,
            "source_type": "PNG",
            "page_count": 1,
        },
        now=clock,
        project_id="CPD-TEST",
    )
    flow = CivilWorkflow(project, now=clock)
    flow.set_crop(CropRegion(0, 0, 200, 150))
    if calibrated:
        flow.apply_calibration(
            scale_point_1=PixelPoint(0, 100),
            scale_point_2=PixelPoint(100, 100),
            known_distance_m=10.0,
            origin_pixel=PixelPoint(50, 100),
            east_reference=PixelPoint(100, 100),
            origin_east_m=1000.0,
            origin_north_m=2000.0,
        )
    return project, flow


def add_approved(
    flow: CivilWorkflow,
    *,
    pixel: PixelPoint = PixelPoint(60, 90),
    elevation: float = 49.06,
    point_type: str = C.EXISTING_GROUND,
):
    point = flow.add_manual_point(
        pixel=pixel, elevation=elevation, point_type=point_type
    )
    flow.approve_point(point.id)
    return point
