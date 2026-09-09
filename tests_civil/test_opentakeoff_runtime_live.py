from __future__ import annotations

import os
import unittest
from pathlib import Path

from screen2xyz_civil.agent_session import new_agent_session
from screen2xyz_civil.opentakeoff_runtime import auto_trace_area, probe_opentakeoff

from .helpers_civil import fresh_dir


RUN_LIVE = os.environ.get("SCREEN2XYZ_RUN_OPENTAKEOFF_LIVE") == "1"
NOW = "2026-09-02T20:00:00+00:00"


def make_closed_room_pdf(path: Path) -> Path:
    """Create a tiny owned synthetic vector PDF with one closed room rectangle."""

    content = (
        "100 100 m 300 100 l 300 300 l 100 300 l h S "
        "BT /F1 14 Tf 180 190 Td (ROOM 101) Tj ET"
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


@unittest.skipUnless(
    RUN_LIVE,
    "real OpenTakeoff protocol smoke test requires SCREEN2XYZ_RUN_OPENTAKEOFF_LIVE=1",
)
class OpenTakeoffRuntimeLiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_process_exposes_required_tool_contract(self):
        probe = await probe_opentakeoff()
        self.assertTrue(probe.available, probe.to_dict())
        self.assertTrue(probe.compatible, probe.to_dict())
        self.assertIn("one_click", probe.tools)
        self.assertIn("view_sheet", probe.tools)

    async def test_real_one_click_returns_reviewable_closed_polygon(self):
        root = fresh_dir()
        pdf = make_closed_room_pdf(root / "closed-room.pdf")
        session = new_agent_session(
            pdf,
            page_number=1,
            page_label="SYN-01",
            name="OpenTakeoff live synthetic",
            now=NOW,
            render_dpi=150,
        )
        # Resolve the synthetic whole-sheet scale. Verification is deliberately
        # not claimed here: this test proves engine/protocol/coordinate flow,
        # not estimator scale acceptance.
        session.set_scale_ratio(100, now=NOW, basis="synthetic test scale 1:100")

        # The PDF rectangle is x=100..300, y(bottom-left)=100..300. In our
        # canonical top-left frame its y range is 492..692, so (200, 592) is
        # safely inside.
        trace = await auto_trace_area(
            session,
            x=200,
            y=592,
            coordinate_frame="pdf_points",
            sensitivity=0.5,
        )
        self.assertGreaterEqual(trace["nverts"], 3, trace)
        self.assertEqual(trace["engine"], "OpenTakeoff")
        self.assertEqual(len(trace["geometry_pdf_points"]), trace["nverts"])
        self.assertTrue(
            trace.get("area_sf") is not None or trace.get("area_px2") is not None,
            trace,
        )


if __name__ == "__main__":
    unittest.main()
