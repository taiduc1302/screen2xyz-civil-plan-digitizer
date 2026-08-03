from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from screen2xyz_app.mapping import ChannelMapping, ChannelSource
from screen2xyz_app.profiles import MappingProfileStore


class MappingTests(unittest.TestCase):
    def mapping(self) -> ChannelMapping:
        return ChannelMapping({
            "x": ChannelSource(
                "screen_zone_ocr", (10, 20, 100, 30),
                numeric_range=(2_300_000.0, 2_500_000.0),
            ),
            "y": ChannelSource(
                "screen_zone_ocr", (10, 60, 100, 30),
                numeric_range=(1_200_000.0, 1_400_000.0),
            ),
            "z": ChannelSource(
                "plan_label_ocr", numeric_range=(40.0, 60.0)
            ),
            "description": ChannelSource("manual", data_type="text"),
        })

    def test_mapping_round_trip_and_mode(self) -> None:
        mapping = self.mapping()
        mapping.validate()
        self.assertTrue(mapping.click_driven)
        self.assertFalse(mapping.automatic)
        self.assertEqual(ChannelMapping.from_json(mapping.to_json()), mapping)

    def test_m2_source_config_reuse(self) -> None:
        sources = self.mapping().m2_sources()
        self.assertEqual([source.semantic_role for source in sources], ["x", "y"])
        self.assertEqual(sources[0].coordinate_basis, "monitor")

    def test_named_profile_is_project_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = MappingProfileStore(Path(temporary))
            path = store.save("Status bar", self.mapping())
            self.assertTrue(path.is_file())
            self.assertEqual(store.names(), ["Status bar"])
            self.assertEqual(store.load("Status bar"), self.mapping())

    def test_out_of_range_value_is_rejected_by_capture_pipeline(self) -> None:
        from screen2xyz_app.capture import CapturePipeline, Reading

        mapping = ChannelMapping({
            "x": ChannelSource("manual", numeric_range=(0.0, 10.0)),
            "y": ChannelSource("manual", numeric_range=(0.0, 10.0)),
            "z": ChannelSource("manual", numeric_range=(40.0, 60.0)),
        })
        values = {"x": "1", "y": "2", "z": "120"}
        with self.assertRaisesRegex(ValueError, "OUT_OF_RANGE"):
            CapturePipeline(
                mapping,
                lambda column, source, context: Reading(values[column], 0.9),
            ).read()

    def test_required_channels_are_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required"):
            ChannelMapping({"x": ChannelSource("manual")}).validate()


if __name__ == "__main__":
    unittest.main()
