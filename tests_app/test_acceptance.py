from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from screen2xyz_app.capture import Reading
from screen2xyz_app.controller import CaptureSessionController
from screen2xyz_app.mapping import ChannelMapping, ChannelSource


class AcceptanceScenarioTests(unittest.TestCase):
    def test_screen_xy_plus_plan_label_z_reaches_sqlite_and_xlsx(self):
        mapping = ChannelMapping({
            "x": ChannelSource("screen_zone_ocr", (100, 100, 80, 20)),
            "y": ChannelSource("screen_zone_ocr", (200, 100, 80, 20)),
            "z": ChannelSource("plan_label_ocr"),
        })
        values = {"x": "432100.25", "y": "5456789.75", "z": "49.78"}
        with tempfile.TemporaryDirectory() as temporary:
            controller = CaptureSessionController(
                Path(temporary), mapping,
                reader=lambda column, source, context: Reading(values[column], 0.91),
            )
            point = controller.capture_click()
            self.assertEqual((point.x, point.y, point.z), (432100.25, 5456789.75, 49.78))
            self.assertEqual(len(controller.store.points(controller.session_id)), 1)
            output = controller.export_xlsx(Path(temporary) / "points.xlsx")
            workbook = load_workbook(output, data_only=True)
            self.assertEqual(workbook["Points"]["D2"].value, 49.78)
            controller.close()


if __name__ == "__main__":
    unittest.main()
