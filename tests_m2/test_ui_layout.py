from __future__ import annotations

import unittest

from screen2xyz_m2.ui.layout import (backend_explanation,
                                     classify_capture_test, format_elapsed,
                                     mini_controller_position, pause_message,
                                     picker_scale_factor, value_row)


class LayoutTests(unittest.TestCase):
    def test_format_elapsed(self):
        self.assertEqual(format_elapsed(0), "00:00:00")
        self.assertEqual(format_elapsed(3661), "01:01:01")

    def test_mini_avoids_regions(self):
        # a region covering the top-left corner forces another corner
        regions = [(0, 0, 400, 300)]
        pos = mini_controller_position(regions, 1920, 1080)
        self.assertIsNotNone(pos)
        self.assertFalse(_overlaps(pos, regions[0]))

    def test_mini_none_when_all_corners_blocked(self):
        regions = [(0, 0, 1920, 1080)]
        self.assertIsNone(mini_controller_position(regions, 1920, 1080))

    def test_mini_default_corner_when_no_regions(self):
        pos = mini_controller_position([], 1920, 1080)
        self.assertEqual(pos, (12, 12))

    def test_pause_messages_are_sentences_with_actions(self):
        for reason in ("USER_REQUEST", "TARGET_UNAVAILABLE",
                       "DISPLAY_INVALIDATED", "BACKEND_BLANK_STREAK",
                       "WORKER_FAILURE_STREAK", "DISK_LIMIT"):
            sentence, actions = pause_message(reason)
            self.assertTrue(sentence[0].isupper())
            self.assertNotIn("_", sentence)  # no raw codes in the sentence
            self.assertTrue(actions)

    def test_value_row_dash_for_missing(self):
        name, shown, status = value_row("Lon", {"normalized_value": None,
                                                "value_status":
                                                "MISSING_SOURCE_VALUE"})
        self.assertEqual(shown, "—")
        name, shown, status = value_row("Lon", {"normalized_value": "1.5",
                                                "value_status": "OK"})
        self.assertEqual(shown, "1.5")


class CaptureTestClassificationTests(unittest.TestCase):
    def test_content_detected_is_pass(self):
        verdict, _ = classify_capture_test("OK", "CONTENT_DETECTED", False)
        self.assertEqual(verdict, "PASS")

    def test_near_uniform_dark_is_fail_never_pass(self):
        # The exact failure the owner's real-target evidence showed: a black
        # PrintWindow frame must never be reported as a successful capture.
        verdict, explanation = classify_capture_test(
            "OK", "NEAR_UNIFORM_DARK", False)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("cannot see", explanation)

    def test_near_uniform_light_is_fail(self):
        verdict, _ = classify_capture_test("OK", "NEAR_UNIFORM_LIGHT", False)
        self.assertEqual(verdict, "FAIL")

    def test_near_uniform_other_is_warning_not_pass(self):
        verdict, _ = classify_capture_test("OK", "NEAR_UNIFORM_OTHER", False)
        self.assertEqual(verdict, "WARNING")

    def test_no_backend_usable_is_fail_even_with_content_detected(self):
        # no_backend_usable is the worker's own explicit "nothing worked"
        # signal from Resolve-And-Capture; it must override any status.
        verdict, _ = classify_capture_test("OK", "CONTENT_DETECTED", True)
        self.assertEqual(verdict, "FAIL")

    def test_target_unavailable_is_fail_with_explanation(self):
        verdict, explanation = classify_capture_test(
            "TARGET_UNAVAILABLE", "NOT_EVALUATED", False)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("not available", explanation)

    def test_target_minimized_is_fail(self):
        verdict, explanation = classify_capture_test(
            "TARGET_MINIMIZED", "NOT_EVALUATED", False)
        self.assertEqual(verdict, "FAIL")
        self.assertIn("minimized", explanation)

    def test_backend_failure_is_fail(self):
        verdict, _ = classify_capture_test("BACKEND_FAILURE",
                                           "NOT_EVALUATED", False)
        self.assertEqual(verdict, "FAIL")


class BackendExplanationTests(unittest.TestCase):
    def test_explicit_backend_never_mentions_auto_resolution(self):
        text = backend_explanation("printwindow_clientonly", None)
        self.assertIn("explicitly chosen", text)
        self.assertNotIn("Auto", text)

    def test_auto_unresolved(self):
        text = backend_explanation("auto", None)
        self.assertIn("not yet resolved", text)

    def test_auto_resolved_printwindow(self):
        text = backend_explanation("auto", "printwindow_clientonly")
        self.assertIn("PrintWindow", text)
        self.assertIn("covers it", text)

    def test_auto_resolved_copyfromscreen_warns_about_visibility(self):
        text = backend_explanation("auto", "copyfromscreen")
        self.assertIn("CopyFromScreen", text)
        self.assertIn("uncovered", text)


class PickerScaleFactorTests(unittest.TestCase):
    def test_small_image_needs_no_scaling(self):
        self.assertEqual(picker_scale_factor(800, 600), 1)

    def test_large_image_scales_down_to_fit(self):
        factor = picker_scale_factor(3840, 2160, max_w=1200, max_h=700)
        self.assertGreaterEqual(factor, 2)
        # Downscaled dimensions must actually fit the requested bounds.
        self.assertLessEqual(3840 / factor, 1200)
        self.assertLessEqual(2160 / factor, 700)

    def test_never_returns_less_than_one(self):
        self.assertEqual(picker_scale_factor(0, 0), 1)


def _overlaps(pos, region) -> bool:
    px, py = pos
    rx, ry, rw, rh = region
    pw, ph = 260, 60
    return not (px + pw <= rx or rx + rw <= px
                or py + ph <= ry or ry + rh <= py)


class UiImportTests(unittest.TestCase):
    def test_app_module_imports_without_display(self):
        # importing must not require a Tk display
        import importlib
        module = importlib.import_module("screen2xyz_m2.ui.app")
        self.assertTrue(hasattr(module, "launch"))

    def test_cli_recover_and_validate_wired(self):
        from screen2xyz_m2.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["recover", "some-run"])
        self.assertEqual(args.command, "recover")
        self.assertEqual(args.run_dir, "some-run")
        args2 = parser.parse_args(["validate-real-target"])
        self.assertEqual(args2.command, "validate-real-target")

    def test_cli_demo_subcommand_wired(self):
        from screen2xyz_m2.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["demo"])
        self.assertEqual(args.command, "demo")
        self.assertFalse(args.interactive)
        args2 = parser.parse_args(["demo", "--interactive"])
        self.assertTrue(args2.interactive)
