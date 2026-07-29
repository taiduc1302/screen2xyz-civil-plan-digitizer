from __future__ import annotations

import unittest

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.models import (SessionDefaults, SourceConfig,
                                  ValidationError, new_source_id,
                                  validate_source, validate_source_set,
                                  xyz_eligibility, xyz_missing_axes)
from screen2xyz_m2.paths import UnsafePath, new_run_id, resolve_under
from screen2xyz_m2.statemachine import IllegalAction, SessionStateMachine


def make_source(**overrides) -> SourceConfig:
    base = dict(source_id=new_source_id(), display_name="Longitude",
                data_type="number", semantic_role="none",
                rect=(10, 10, 180, 28))
    base.update(overrides)
    return SourceConfig(**base)


class SourceValidationTests(unittest.TestCase):
    def test_valid_source_passes(self):
        validate_source(make_source(), scope_size=(900, 300))

    def test_region_bounds(self):
        with self.assertRaises(ValidationError):
            validate_source(make_source(rect=(0, 0, 7, 20)))
        with self.assertRaises(ValidationError):
            validate_source(make_source(rect=(0, 0, 2001, 20)))
        with self.assertRaises(ValidationError):
            validate_source(make_source(rect=(0, 0, 100, 801)))
        with self.assertRaises(ValidationError):
            validate_source(make_source(rect=(800, 10, 200, 28)),
                            scope_size=(900, 300))

    def test_display_name_bounds(self):
        with self.assertRaises(ValidationError):
            validate_source(make_source(display_name=""))
        with self.assertRaises(ValidationError):
            validate_source(make_source(display_name="x" * 81))

    def test_role_requires_number_type(self):
        with self.assertRaises(ValidationError):
            validate_source(make_source(data_type="auto", semantic_role="x"))
        with self.assertRaises(ValidationError):
            validate_source(make_source(data_type="text", semantic_role="z"))

    def test_threshold_only_for_number(self):
        with self.assertRaises(ValidationError):
            validate_source(make_source(data_type="text",
                                        min_change_threshold=0.5))

    def test_upscale_bounds(self):
        with self.assertRaises(ValidationError):
            validate_source(make_source(upscale_factor=5))

    def test_source_id_pattern(self):
        with self.assertRaises(ValidationError):
            validate_source(make_source(source_id="..\\evil"))

    def test_set_rules(self):
        a = make_source(display_name="A", semantic_role="x")
        b = make_source(display_name="B", semantic_role="y")
        c = make_source(display_name="C", semantic_role="z")
        validate_source_set([a, b, c], scope_size=(900, 300))
        with self.assertRaises(ValidationError):
            validate_source_set([a, make_source(display_name="A")])
        with self.assertRaises(ValidationError):
            validate_source_set(
                [a, make_source(display_name="B", semantic_role="x")])
        with self.assertRaises(ValidationError):
            validate_source_set([])
        nine = [make_source(display_name=f"S{i}") for i in range(9)]
        with self.assertRaises(ValidationError):
            validate_source_set(nine)

    def test_json_round_trip(self):
        source = make_source(numeric_range=(-180.0, 180.0),
                             decimal_precision_max=6, confirmations=2)
        clone = SourceConfig.from_json(source.to_json())
        self.assertEqual(clone.to_json(), source.to_json())

    def test_xyz_eligibility(self):
        a = make_source(display_name="A", semantic_role="x")
        b = make_source(display_name="B", semantic_role="y")
        c = make_source(display_name="C", semantic_role="z")
        result = xyz_eligibility([a, b, c])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["x_source_id"], a.source_id)
        self.assertFalse(xyz_eligibility([a, b])["eligible"])
        c_disabled = make_source(display_name="C", semantic_role="z",
                                 enabled=False)
        self.assertFalse(xyz_eligibility([a, b, c_disabled])["eligible"])

    def test_coordinate_type_holds_xyz_roles(self):
        # Phase 2 (2026-07-19): `coordinate` (Phase 1) produces the same
        # decimal-degrees numeric output `number` does - a lat/long field
        # needs it for OCR-corruption safety and must still be eligible
        # for X/Y/Z, or the two features would be mutually exclusive.
        a = make_source(display_name="Lat", data_type="coordinate",
                        semantic_role="x")
        validate_source(a, scope_size=(900, 300))
        b = make_source(display_name="Long", data_type="coordinate",
                        semantic_role="y")
        c = make_source(display_name="Elev", data_type="number",
                        semantic_role="z")
        result = xyz_eligibility([a, b, c])
        self.assertTrue(result["eligible"])
        self.assertEqual(xyz_missing_axes([a, b]), ["Z"])

    def test_line_part_requires_non_negative(self):
        validate_source(make_source(line_part=0), scope_size=(900, 300))
        validate_source(make_source(line_part=2), scope_size=(900, 300))
        with self.assertRaises(ValidationError):
            validate_source(make_source(line_part=-1))

    def test_line_part_json_round_trip(self):
        source = make_source(line_part=1)
        clone = SourceConfig.from_json(source.to_json())
        self.assertEqual(clone.line_part, 1)
        default = make_source()
        self.assertIsNone(SourceConfig.from_json(default.to_json()).line_part)


class DefaultsTests(unittest.TestCase):
    def test_defaults_match_contracts(self):
        defaults = SessionDefaults()
        defaults.validate()
        self.assertEqual(defaults.interval_ms, 1000)
        self.assertEqual(defaults.retention_mode, "changed_and_errors")
        self.assertEqual(defaults.confirmations, 1)
        self.assertEqual(defaults.debounce_ms, 0)
        self.assertIsNone(defaults.min_change_threshold)
        self.assertFalse(defaults.cursor_metadata)

    def test_bounds(self):
        with self.assertRaises(ValidationError):
            SessionDefaults(interval_ms=249).validate()
        with self.assertRaises(ValidationError):
            SessionDefaults(interval_ms=10001).validate()
        with self.assertRaises(ValidationError):
            SessionDefaults(retention_mode="everything").validate()
        with self.assertRaises(ValidationError):
            SessionDefaults(confirmations=6).validate()


class PathsTests(unittest.TestCase):
    def test_run_id_shape(self):
        self.assertRegex(new_run_id(), r"^m2-\d{8}T\d{6}Z-[0-9a-f]{6}$")

    def test_traversal_rejected(self):
        from pathlib import Path
        with self.assertRaises(UnsafePath):
            resolve_under(Path("."), "../escape")
        with self.assertRaises(UnsafePath):
            resolve_under(Path("."), "..")


class StateMachineTests(unittest.TestCase):
    def machine_at(self, state: str) -> SessionStateMachine:
        machine = SessionStateMachine()
        machine.select_target()
        if state == "TARGET_SELECTED":
            return machine
        machine.sources_configured()
        if state == "REGIONS_CONFIGURED":
            return machine
        machine.confirm_preview()
        if state == "ARMED":
            return machine
        machine.start_recording()
        if state == "RECORDING":
            return machine
        machine.pause()
        if state == "PAUSED":
            return machine
        raise AssertionError(state)

    def test_happy_path(self):
        machine = self.machine_at("RECORDING")
        self.assertEqual(machine.state, "RECORDING")
        machine.pause()
        machine.resume()
        machine.stop()
        self.assertEqual(machine.state, "STOPPING")
        machine.finalized()
        self.assertEqual(machine.state, "FINALIZED")

    def test_capture_illegal_outside_recording(self):
        for state in ("TARGET_SELECTED", "REGIONS_CONFIGURED", "ARMED"):
            machine = self.machine_at(state)
            self.assertFalse(machine.is_legal("pause"))

    def test_snapshot_only_pre_arm(self):
        self.assertTrue(
            self.machine_at("REGIONS_CONFIGURED").is_legal("region_snapshot"))
        self.assertFalse(self.machine_at("ARMED").is_legal("region_snapshot"))
        self.assertFalse(
            self.machine_at("RECORDING").is_legal("region_snapshot"))

    def test_preview_only_regions_configured(self):
        self.assertTrue(
            self.machine_at("REGIONS_CONFIGURED").is_legal("preview"))
        self.assertFalse(self.machine_at("PAUSED").is_legal("preview"))

    def test_stale_preview_blocks_start(self):
        machine = self.machine_at("ARMED")
        machine.sources_configured()          # edit disarms
        self.assertEqual(machine.state, "REGIONS_CONFIGURED")
        machine.confirm_preview()
        machine.configuration_revision += 1   # simulate late edit
        with self.assertRaises(IllegalAction):
            machine.start_recording()

    def test_reconfigure_from_paused(self):
        machine = self.machine_at("PAUSED")
        machine.reconfigure()
        self.assertEqual(machine.state, "REGIONS_CONFIGURED")
        self.assertIsNone(machine.preview_confirmed_revision)

    def test_setup_worker_blocked_interlock(self):
        machine = self.machine_at("REGIONS_CONFIGURED")
        machine.setup_worker_blocked = True
        for action in ("region_snapshot", "preview", "confirm_preview"):
            self.assertFalse(machine.is_legal(action), action)
        self.assertTrue(machine.is_legal("retry_worker"))
        self.assertTrue(machine.is_legal("save_profile"))
        self.assertTrue(machine.is_legal("close"))
        machine.setup_worker_blocked = False
        self.assertFalse(machine.is_legal("retry_worker"))

    def test_edit_in_armed_disarms_via_transition(self):
        machine = self.machine_at("ARMED")
        machine.sources_configured()
        self.assertEqual(machine.state, "REGIONS_CONFIGURED")
        self.assertIsNone(machine.preview_confirmed_revision)


class ContractsSanityTests(unittest.TestCase):
    def test_enums_closed_and_distinct(self):
        self.assertEqual(len(C.WORKER_COMMANDS), 12)
        self.assertNotIn("SKIPPED_TICK", C.VALUE_STATUSES)
        self.assertNotIn("status", dir(C))
        self.assertEqual(C.RETENTION_DEFAULT, "changed_and_errors")
        self.assertEqual(C.RESTART_BACKOFF_MS, (0, 1000, 5000))
        self.assertEqual(C.RAW_OCR_MAX_BYTES, 4096)

    def test_retainable_set_excludes_missing_and_unstable(self):
        self.assertNotIn("MISSING_SOURCE_VALUE",
                         C.RETAINABLE_ERROR_VALUE_STATUSES)
        self.assertNotIn("UNSTABLE_READING",
                         C.RETAINABLE_ERROR_VALUE_STATUSES)
