"""Usability: no raw internal code is shown to a non-developer owner.

A multi-persona usability evaluation found the UI leaked raw snake_case enum
values and SCREAMING_SNAKE status codes straight to the user in several
controls (backend dropdown, retention dropdown, field-card status, live-feed
Status column and headers, Saved-CSV headers, capture-test failures). These
tests pin the plain-language layer that fixes that, and guard against new
leaks.
"""

from __future__ import annotations

import re
import unittest

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.ui import layout as L

# A raw internal code is an all-caps or snake_case token with no spaces (e.g.
# "AMBIGUOUS_MULTIPLE_NUMBERS", "printwindow_clientonly"). A humanized label
# always contains a space or is a deliberately short friendly word.
_RAW_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)+$")


def _looks_raw(text: str) -> bool:
    return bool(_RAW_CODE.match(text.strip()))


class BackendLabelTests(unittest.TestCase):
    def test_every_backend_choice_has_a_friendly_label(self):
        for value in ("auto", "printwindow_clientonly", "copyfromscreen"):
            label = L.backend_label(value)
            self.assertFalse(_looks_raw(label),
                             f"{value!r} leaked raw label {label!r}")

    def test_backend_label_matches_help_wording(self):
        self.assertEqual(L.backend_label("printwindow_clientonly"),
                         "PrintWindow")
        self.assertEqual(L.backend_label("copyfromscreen"), "CopyFromScreen")

    def test_backend_round_trip_label_to_value(self):
        for value in ("auto", "printwindow_clientonly", "copyfromscreen"):
            self.assertEqual(L.backend_value(L.backend_label(value)), value)

    def test_backend_value_is_identity_safe_for_unknown(self):
        self.assertEqual(L.backend_value("printwindow_clientonly"),
                         "printwindow_clientonly")

    def test_none_backend_reads_as_plain_english(self):
        self.assertNotIn("_", L.backend_label(None))


class RetentionLabelTests(unittest.TestCase):
    def test_every_retention_mode_has_a_friendly_label(self):
        for key in C.RETENTION_MODES:
            label = L.retention_label(key)
            self.assertFalse(_looks_raw(label),
                             f"{key!r} leaked raw label {label!r}")

    def test_retention_round_trip_label_to_key(self):
        for key in C.RETENTION_MODES:
            self.assertEqual(L.retention_key(L.retention_label(key)), key)

    def test_retention_key_is_identity_safe(self):
        self.assertEqual(L.retention_key("changed_and_errors"),
                         "changed_and_errors")


class StatusLabelTests(unittest.TestCase):
    def test_every_value_status_is_humanized(self):
        for code in C.VALUE_STATUSES:
            label = L.value_status_label(code)
            self.assertFalse(_looks_raw(label),
                             f"value_status {code!r} leaked {label!r}")

    def test_every_stability_status_is_humanized(self):
        for code in C.STABILITY_STATUSES:
            label = L.stability_label(code)
            self.assertFalse(_looks_raw(label),
                             f"stability {code!r} leaked {label!r}")

    def test_every_content_status_is_humanized(self):
        for code in C.CONTENT_STATUSES:
            label = L.content_status_label(code)
            self.assertFalse(_looks_raw(label),
                             f"content {code!r} leaked {label!r}")

    def test_ambiguous_multiple_numbers_reads_plainly(self):
        self.assertIn("number", L.value_status_label(
            "AMBIGUOUS_MULTIPLE_NUMBERS").lower())

    def test_field_card_status_drops_empty_parts_and_humanizes(self):
        line = L.field_card_status("OK", "IMMEDIATE", "Persisted to journal")
        self.assertNotIn("IMMEDIATE", line)
        self.assertIn("Persisted to journal", line)
        # NOT_EVALUATED contributes nothing rather than an empty "· ·".
        line2 = L.field_card_status("OK", "NOT_EVALUATED", "Observed live")
        self.assertNotIn(" ·  · ", line2)


class ColumnTitleTests(unittest.TestCase):
    def test_no_feed_column_header_is_raw(self):
        for col in L.FEED_COLUMNS:
            title = L.feed_column_title(col)
            self.assertFalse(_looks_raw(title),
                             f"feed column {col!r} leaked header {title!r}")

    def test_specific_feed_headers_are_friendly(self):
        self.assertEqual(L.feed_column_title("value_status"), "Status")
        self.assertEqual(L.feed_column_title("live_csv"), "Live CSV")
        self.assertEqual(L.feed_column_title("raw_ocr"), "Raw OCR")

    def test_csv_preview_titles_humanize_internal_columns(self):
        self.assertEqual(L.csv_preview_title("monotonic_offset_ms"),
                         "Offset (ms)")
        self.assertEqual(L.csv_preview_title("event_seq"), "Event #")
        # A per-field dynamic column is passed through untouched.
        self.assertEqual(L.csv_preview_title("Depth [VALUE]"), "Depth [VALUE]")


class CaptureTestVerdictTests(unittest.TestCase):
    def test_remaining_hard_failures_get_a_plain_sentence_not_a_bare_code(self):
        for status in ("BACKEND_FAILURE", "PAYLOAD_TOO_LARGE",
                       "REGION_OUT_OF_BOUNDS", "DISPLAY_INVALIDATED"):
            verdict, text = L.classify_capture_test(status, "NOT_EVALUATED",
                                                    False)
            self.assertEqual(verdict, "FAIL")
            # The message is a real sentence with a remedy, not just the code.
            self.assertNotEqual(text.strip(), status)
            self.assertNotEqual(text.strip(), f"Capture failed ({status}).")
            self.assertTrue(text[0].isupper() and " " in text,
                            f"{status} produced non-sentence {text!r}")
            # Raw code kept only as a parenthetical hint.
            self.assertIn(f"({status})", text)

    def test_content_detected_still_passes(self):
        verdict, _ = L.classify_capture_test("OK", "CONTENT_DETECTED", False)
        self.assertEqual(verdict, "PASS")


class ColorLegendTests(unittest.TestCase):
    def test_legend_covers_all_six_feed_colors_including_yellow(self):
        colors = {c for c, _ in L.FEED_COLOR_LEGEND}
        self.assertEqual(colors,
                         {"gray", "blue", "green", "orange", "yellow", "red"})


class PauseGuidanceTests(unittest.TestCase):
    """Every pause the owner can hit while recording gets either a concrete
    'what to do first' instruction, or an empty string when the recovery bar
    already guides it (resize/DPI) or the action is self-evident (they
    pressed Pause). No pause may leave the owner with a Resume button and no
    idea why it keeps re-pausing."""

    def test_minimized_pause_tells_owner_to_restore_the_window(self):
        self.assertIn("Restore",
                      L.pause_guidance("TARGET_MINIMIZED_STREAK"))

    def test_blank_pause_mentions_uncovering_or_switching_backend(self):
        text = L.pause_guidance("BACKEND_BLANK_STREAK").lower()
        self.assertTrue("uncover" in text or "copyfromscreen" in text)

    def test_disk_pause_reassures_data_is_saved(self):
        text = L.pause_guidance("DISK_LIMIT").lower()
        self.assertIn("disk", text)
        self.assertIn("stop", text)

    def test_user_pause_and_repreview_need_no_extra_guidance(self):
        # Manual pause is self-evident; resize/DPI is handled by the
        # recovery bar - both intentionally empty here.
        self.assertEqual(L.pause_guidance("USER_REQUEST"), "")
        self.assertEqual(L.pause_guidance("DISPLAY_INVALIDATED"), "")

    def test_unknown_pause_still_gets_a_safe_default(self):
        self.assertTrue(L.pause_guidance("SOMETHING_NEW"))


class ValueStatusGuidanceTests(unittest.TestCase):
    """Phase 4.1 (2026-07-19): the recording screen's field cards used to
    show the SAME generic 'capture/OCR issue' text for every warning
    colour - a non-technical owner couldn't tell a too-tight region from a
    wrong decimal separator from a genuinely gone window. Every reachable
    failure status must now get its own concrete next step, mirroring
    pause_guidance's already-established pattern."""

    # OK needs no guidance (nothing is wrong); MISSING_SOURCE_VALUE is
    # live-only by design (see stability.py and the guide's hover note) -
    # both intentionally empty. Every other value_status is a real,
    # reachable failure and must give the owner something to try.
    _NO_GUIDANCE_NEEDED = frozenset({"OK", "MISSING_SOURCE_VALUE"})

    def test_every_failure_status_gets_concrete_guidance(self):
        for code in C.VALUE_STATUSES:
            guidance = L.value_status_guidance(code)
            if code in self._NO_GUIDANCE_NEEDED:
                self.assertEqual(guidance, "", f"{code!r} should be empty")
            else:
                self.assertTrue(
                    guidance, f"{code!r} has no actionable guidance")
                self.assertFalse(_looks_raw(guidance),
                                 f"{code!r} guidance leaked a raw code")

    def test_ambiguous_multiple_numbers_says_redraw_tighter(self):
        text = L.value_status_guidance("AMBIGUOUS_MULTIPLE_NUMBERS").lower()
        self.assertIn("redraw", text)

    def test_suspect_glyph_confusion_hints_at_misread_symbol(self):
        text = L.value_status_guidance("SUSPECT_GLYPH_CONFUSION").lower()
        self.assertIn("misread", text)

    def test_target_unavailable_points_to_recovery_bar(self):
        text = L.value_status_guidance("TARGET_UNAVAILABLE").lower()
        self.assertIn("recovery bar", text)


class MissingValueEscalationTests(unittest.TestCase):
    """Phase 4.2 (2026-07-19): a field at realistic small on-screen text
    with all defaults must get a value or an actionable message - never a
    silent 'No value yet' forever. A brief hover-driven absence (§5k Phase
    2.3) must NOT look like an error; a field that never gets a value
    across many ticks must eventually say so with a concrete next step."""

    def test_below_threshold_is_silent(self):
        for streak in (0, 1, 5, L.MISSING_VALUE_HINT_TICKS - 1):
            self.assertEqual(L.missing_value_guidance(streak), "",
                             f"streak={streak} should stay silent")

    def test_at_and_above_threshold_gives_actionable_message(self):
        for streak in (L.MISSING_VALUE_HINT_TICKS,
                      L.MISSING_VALUE_HINT_TICKS + 1,
                      L.MISSING_VALUE_HINT_TICKS * 3):
            text = L.missing_value_guidance(streak)
            self.assertTrue(text, f"streak={streak} should have guidance")
            self.assertIn("region", text.lower())

    def test_message_reports_the_actual_streak_count(self):
        text = L.missing_value_guidance(L.MISSING_VALUE_HINT_TICKS)
        self.assertIn(str(L.MISSING_VALUE_HINT_TICKS), text)


class XyzWordingTests(unittest.TestCase):
    """XYZ is optional; its status must read as optional (not a hard error),
    use the UI word 'field' (not 'source'/'role x'), and report ALL missing
    axes at once instead of one per attempt."""

    def test_eligible_reads_positively(self):
        text = L.xyz_status_sentence(True, [])
        self.assertIn("ELIGIBLE", text)

    def test_not_eligible_is_framed_optional_and_lists_all_axes(self):
        text = L.xyz_status_sentence(False, ["Y", "Z"])
        self.assertIn("optional", text.lower())
        self.assertIn("Y, Z", text)
        self.assertNotIn("source", text.lower())
        self.assertNotIn("role x", text.lower())

    def test_missing_axes_computed_from_sources(self):
        from screen2xyz_m2.models import SourceConfig, xyz_missing_axes
        # Only X assigned (as a number) -> Y and Z missing.
        sources = [SourceConfig(source_id="a", display_name="X",
                               data_type="number", semantic_role="x")]
        self.assertEqual(xyz_missing_axes(sources), ["Y", "Z"])

    def test_written_outcome_is_green_and_counts_points(self):
        sentence, colour = L.xyz_outcome_sentence(
            {"written": True, "row_count": 12, "excluded_event_count": 0})
        self.assertIn("WRITTEN", sentence)
        self.assertIn("12", sentence)
        self.assertEqual(colour, "#1a7f37")

    def test_not_produced_outcome_is_amber_and_plain(self):
        sentence, colour = L.xyz_outcome_sentence(
            {"written": False,
             "reason": "exactly one enabled number source must hold role x"})
        self.assertIn("optional", sentence.lower())
        self.assertNotIn("role x", sentence.lower())
        self.assertEqual(colour, "#b58900")


class WarningSentenceTests(unittest.TestCase):
    def test_known_code_becomes_plain_with_detail_kept(self):
        text = L.warning_sentence(
            "FINAL_CSV_ROW_COUNT_MISMATCH: 30 CSV rows vs 42 journal events")
        self.assertIn("missing from the final CSV", text)
        self.assertIn("(30 CSV rows vs 42 journal events)", text)

    def test_unknown_code_is_never_shown_raw(self):
        text = L.warning_sentence("SOME_NEW_WARNING_CODE")
        self.assertFalse(_looks_raw(text))


if __name__ == "__main__":
    unittest.main()
