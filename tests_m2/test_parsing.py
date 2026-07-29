from __future__ import annotations

import unittest

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.parsing import (ParseOutcome, bound_raw,
                                   looks_like_alphanumeric_code,
                                   looks_like_coordinate, parse_auto,
                                   parse_coordinate, parse_for_source,
                                   parse_number, parse_text)


class RawBoundTests(unittest.TestCase):
    def test_short_text_untouched(self):
        raw = bound_raw("-123.654321")
        self.assertEqual((raw.raw_text, raw.raw_truncated,
                          raw.raw_original_utf8_bytes),
                         ("-123.654321", False, 11))

    def test_exact_boundary_4096(self):
        text = "a" * C.RAW_OCR_MAX_BYTES
        raw = bound_raw(text)
        self.assertFalse(raw.raw_truncated)
        self.assertEqual(len(raw.raw_text.encode("utf-8")), 4096)

    def test_over_boundary_truncates_with_flag(self):
        raw = bound_raw("b" * 4097)
        self.assertTrue(raw.raw_truncated)
        self.assertEqual(raw.raw_original_utf8_bytes, 4097)
        self.assertEqual(len(raw.raw_text.encode("utf-8")), 4096)

    def test_multibyte_boundary_keeps_complete_code_points(self):
        text = "€" * 1366  # 3 bytes each => 4098 bytes
        raw = bound_raw(text)
        self.assertTrue(raw.raw_truncated)
        encoded = raw.raw_text.encode("utf-8")
        self.assertLessEqual(len(encoded), 4096)
        self.assertEqual(len(encoded) % 3, 0)
        raw.raw_text.encode("utf-8").decode("utf-8")  # must not raise

    def test_truncated_input_never_parses(self):
        raw = bound_raw("1" * 5000)
        outcome = parse_for_source(raw, "number")
        self.assertEqual(outcome.parse_status, "INPUT_TRUNCATED")
        self.assertIsNone(outcome.normalized_value)
        self.assertIn("RAW_OCR_TRUNCATED", outcome.warning_codes)


class NumberParsingTests(unittest.TestCase):
    def ok(self, text: str, expected: str, **kw) -> ParseOutcome:
        outcome = parse_number(text, **kw)
        self.assertEqual((outcome.parse_status, outcome.normalized_value),
                         ("OK", expected), text)
        return outcome

    def status(self, text: str, expected_status: str, **kw) -> ParseOutcome:
        outcome = parse_number(text, **kw)
        self.assertEqual(outcome.parse_status, expected_status, text)
        return outcome

    def test_ascii_negative_and_plus(self):
        self.ok("-123.654321", "-123.654321")
        self.ok("+49.123456", "49.123456")

    def test_unicode_minus_variants_normalized(self):
        for glyph in ("−", "–", "—", "‐", "‑",
                      "‒", "﹣", "－"):
            outcome = self.ok(f"{glyph}123.654321", "-123.654321")
            self.assertTrue(outcome.sign_normalized, repr(glyph))
            self.assertTrue(outcome.original_sign_code_point.startswith("U+"))

    def test_bc_negative_longitude_stays_negative(self):
        self.ok("−123.654321", "-123.654321")

    def test_separated_sign_is_malformed(self):
        self.status("- 123.4", "MALFORMED_NUMBER")
        self.status("− 123.4", "MALFORMED_NUMBER")

    def test_unrecognized_dashlike_sign_is_malformed_not_positive(self):
        # ARABIC-INDIC style or exotic minus-named glyphs must never turn a
        # negative-looking token positive.
        self.status("˗123.4", "MALFORMED_NUMBER")  # MODIFIER MINUS SIGN

    def test_zero_candidates(self):
        self.status("no digits here", "NO_NUMBER")
        self.status("", "NO_NUMBER")

    def test_multiple_candidates_never_auto_picked(self):
        self.status("12.5 77.1", "AMBIGUOUS_MULTIPLE_NUMBERS")

    def test_station_notation_unsupported(self):
        self.status("0+250.00", "AMBIGUOUS_MULTIPLE_NUMBERS")

    def test_space_grouped_number_unsupported(self):
        self.status("1 234.56", "AMBIGUOUS_MULTIPLE_NUMBERS")

    def test_letter_inside_digits_malformed(self):
        self.status("49.1O2345", "MALFORMED_NUMBER")
        self.status("4A.1", "MALFORMED_NUMBER")

    def test_leading_decimal_separator_is_malformed_not_reanchored(self):
        """Independent audit BLOCKER: _TOKEN_RE requires a digit right
        after the optional sign, so a leading decimal/thousands separator
        with no digit before it was silently excluded from the match and
        finditer re-anchored on the digit AFTER it - ".5" parsed as OK "5"
        (10x wrong magnitude) and "-.5" parsed as OK "5" (wrong magnitude
        AND the sign silently dropped). Must fail closed instead."""

        self.status(".5", "MALFORMED_NUMBER")
        self.status("-.5", "MALFORMED_NUMBER")
        self.status(".85", "MALFORMED_NUMBER")
        self.status(",5", "MALFORMED_NUMBER", separator_mode="comma")
        # Sanity: an ordinary embedded decimal point is unaffected.
        self.ok("12.5", "12.5")
        self.ok("-12.5", "-12.5")

    def test_thousands_point_mode(self):
        self.ok("1,234.5", "1234.5")
        self.ok("12,345,678", "12345678")

    def test_comma_mode(self):
        self.ok("1,5", "1.5", separator_mode="comma")
        self.ok("1.234,5", "1234.5", separator_mode="comma")

    def test_auto_separator_ambiguity(self):
        self.status("1,234", "MALFORMED_NUMBER", separator_mode="auto")
        self.ok("1,234.5", "1234.5", separator_mode="auto")

    def test_range(self):
        self.status("181.0", "OUT_OF_RANGE",
                    numeric_range=(-180.0, 180.0))
        self.ok("179.9", "179.9", numeric_range=(-180.0, 180.0))

    def test_precision(self):
        self.status("1.1234567", "MALFORMED_NUMBER", precision_max=6)
        self.ok("1.123456", "1.123456", precision_max=6)

    def test_unit_suffix(self):
        self.status("87.05m", "MALFORMED_NUMBER")  # letter adjacent
        self.ok("87.05 m", "87.05")


class TextAndAutoTests(unittest.TestCase):
    def test_text_normalization(self):
        outcome = parse_text("  a\tb\x07c \n d ")
        self.assertEqual(outcome.normalized_value, "a b c d")
        self.assertEqual(outcome.value_kind, "text")

    def test_auto_single_number(self):
        outcome = parse_auto("  -12.5  ")
        self.assertEqual((outcome.value_kind, outcome.normalized_value),
                         ("number", "-12.5"))

    def test_auto_number_with_substantive_residue_is_text(self):
        outcome = parse_auto("elev 12.5")
        self.assertEqual(outcome.value_kind, "text")

    def test_auto_multiple_numbers_is_text_not_guess(self):
        outcome = parse_auto("12.5 77.1")
        self.assertEqual(outcome.value_kind, "text")
        self.assertEqual(outcome.normalized_value, "12.5 77.1")


class DeriveValueStatusTests(unittest.TestCase):
    def test_causal_precedence(self):
        cases = [
            (("OK", "OK", "OK", "IMMEDIATE"), "OK"),
            (("OK", "EMPTY_TEXT", "NOT_RUN", "NOT_EVALUATED"),
             "MISSING_SOURCE_VALUE"),
            (("OK", "ENGINE_FAILURE", "NOT_RUN", "NOT_EVALUATED"),
             "OCR_FAILURE"),
            (("OK", "OK", "AMBIGUOUS_MULTIPLE_NUMBERS", "NOT_EVALUATED"),
             "AMBIGUOUS_MULTIPLE_NUMBERS"),
            (("OK", "OK", "INPUT_TRUNCATED", "NOT_EVALUATED"),
             "INPUT_TRUNCATED"),
            (("OK", "OK", "OK", "REJECTED"), "UNSTABLE_READING"),
            (("REGION_OUT_OF_BOUNDS", "NOT_RUN_CAPTURE_FAILED", "NOT_RUN",
              "NOT_EVALUATED"), "SOURCE_NOT_VISIBLE"),
            (("TARGET_MINIMIZED", "NOT_RUN_CAPTURE_FAILED", "NOT_RUN",
              "NOT_EVALUATED"), "TARGET_UNAVAILABLE"),
            (("BACKEND_FAILURE", "NOT_RUN_CAPTURE_FAILED", "NOT_RUN",
              "NOT_EVALUATED"), "CAPTURE_FAILURE"),
        ]
        for args, expected in cases:
            self.assertEqual(C.derive_value_status(*args), expected, args)

    def test_worker_failure_dominates(self):
        self.assertEqual(
            C.derive_value_status("OK", "OK", "OK", "IMMEDIATE",
                                  worker_status="REQUEST_TIMEOUT"),
            "CAPTURE_FAILURE")


class CoordinateParsingTests(unittest.TestCase):
    """Real-target finding (owner test against Google Earth, 2026-07-19):
    Windows OCR reliably misread the degree symbol (°) as the digit "0"
    for on-screen coordinate text. A plain "number" field scoped tightly
    to just the degrees portion of a DMS reading (e.g. "49°" -> "490")
    would silently accept the corrupted digit run as a valid number,
    1000x too large, with parse_status "OK" - never flagged. These tests
    pin the fix: structural DMS tokenization (the leading digit run before
    the first '/″ separator is ALWAYS the degrees candidate, whether or
    not a real ° preceded it) plus range validation (degrees <=90 for
    N/S, <=180 otherwise; minutes/seconds <60) - which catches the
    corruption because the value is out of range, not because the parser
    detected the specific glyph mistake (it deliberately never tries to)."""

    def test_the_danger_case_isolated_corrupted_degrees_is_flagged(self):
        # THE bug: "49°" corrupted to "490" (or similar) used to parse as
        # a confidently-wrong OK number. Now caught.
        out = parse_coordinate("49008")
        self.assertEqual(out.parse_status, "SUSPECT_GLYPH_CONFUSION")
        self.assertIsNone(out.normalized_value)

    def test_degree_symbol_read_correctly_just_degrees(self):
        out = parse_coordinate("49°")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.000000")

    def test_full_dms_with_correct_degree_symbol(self):
        out = parse_coordinate("49°08'20.06\"N")
        self.assertEqual(out.parse_status, "OK")
        # 49 + 8/60 + 20.06/3600
        self.assertAlmostEqual(float(out.normalized_value), 49.138906,
                               places=5)

    def test_full_dms_with_corrupted_degree_symbol_recovers_with_label(self):
        # Owner decision 2026-07-21: the FULL corrupted DMS shape (seconds
        # AND hemisphere present, '0' standing exactly where the degree
        # symbol belongs, every component range-valid after the decode) now
        # RECOVERS to the numeric value - always carrying the
        # DEGREE_GLYPH_RECOVERED warning code so it is never silent.
        out = parse_coordinate("49008'20.06\"N")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)

    def test_full_dms_with_dropped_degree_symbol_recovers_unambiguously(self):
        # "4908" contains exactly ONE '0' character, so there is only one
        # possible degrees/minutes split (49/8) - unambiguous, recovers
        # with the label (2026-07-21 owner decision + adversarial-review
        # fix: recovery only fires when exactly one candidate split is
        # physically valid; see test_recovery_declines_when_ambiguous for
        # the multi-'0' case that must NOT recover).
        out = parse_coordinate("4908'20.06\"N")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)

    def test_plain_decimal_degrees(self):
        out = parse_coordinate("49.137")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.137000")

    def test_plain_decimal_degrees_negative_sign(self):
        out = parse_coordinate("-123.654321")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "-123.654321")

    def test_longitude_hemisphere_e_uses_180_bound_and_stays_positive(self):
        out = parse_coordinate("123°03'41.61\"E")
        self.assertEqual(out.parse_status, "OK")
        self.assertGreater(float(out.normalized_value), 0)

    def test_longitude_hemisphere_w_negates(self):
        out = parse_coordinate("123°03'41.61\"W")
        self.assertEqual(out.parse_status, "OK")
        self.assertLess(float(out.normalized_value), 0)

    def test_longitude_corrupted_degree_recovers_negative_with_label(self):
        out = parse_coordinate("123003'41.61\"W")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "-123.061558")
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)

    def test_recovery_never_fires_without_full_dms_context(self):
        # Every guard that keeps the recovery strict: no hemisphere, no
        # seconds, wrong separator digit, or a decode that still fails
        # range validation - all stay FLAGGED, never guessed.
        for text in ("49008'20.06\"",     # no hemisphere letter
                     "49908'20.06\"N",    # separator digit is 9, not 0
                     "95008'20.06\"N"):   # decoded degrees 95 > 90 for N
            out = parse_coordinate(text)
            self.assertEqual(out.parse_status, "SUSPECT_GLYPH_CONFUSION",
                             repr(text))
            self.assertIsNone(out.normalized_value, repr(text))

    def test_recovery_declines_when_the_split_is_genuinely_ambiguous(self):
        # Adversarial review finding: a short run can have more than one
        # '0' that could structurally be the misread degree symbol -
        # "4008" splits validly as EITHER 4deg08min OR 40deg8min, both
        # physically plausible. Recovering either guess would be exactly
        # the silent-wrongness the whole design exists to avoid - must
        # decline (stay flagged), not silently pick one.
        for text in ("4008'20.06\"N",       # 4deg08 vs 40deg8, both valid
                     "5008'20.06\"N",
                     "17008'20.06\"E"):      # ambiguous for E/W (axis 180) too
            out = parse_coordinate(text)
            self.assertEqual(out.parse_status, "SUSPECT_GLYPH_CONFUSION",
                             repr(text))
            self.assertIsNone(out.normalized_value, repr(text))

    def test_recovery_recovers_when_the_run_has_only_one_zero(self):
        # Contrast case: "4908" has exactly one '0', so only one split
        # (49/8) is structurally possible - unambiguous, must recover.
        out = parse_coordinate("4908'20.06\"N")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)

    def test_axis_bound_checks_the_composed_total_not_degrees_alone(self):
        # Adversarial review finding: degrees=90 alone is a valid boundary
        # (a reading exactly at the pole), but 90 PLUS nonzero minutes/
        # seconds is a real position past the pole - physically
        # impossible. The bound must gate the composed decimal total.
        exactly_at_pole = parse_coordinate("90°00'00\"N")
        self.assertEqual(exactly_at_pole.parse_status, "OK")
        self.assertEqual(exactly_at_pole.normalized_value, "90.000000")
        past_the_pole = parse_coordinate("90°08'20.06\"N")
        self.assertEqual(past_the_pole.parse_status,
                         "SUSPECT_GLYPH_CONFUSION")
        recovered_past_the_pole = parse_coordinate("90008'20.06\"N")
        self.assertEqual(recovered_past_the_pole.parse_status,
                         "SUSPECT_GLYPH_CONFUSION")
        past_antimeridian = parse_coordinate("180003'41.61\"W")
        self.assertEqual(past_antimeridian.parse_status,
                         "SUSPECT_GLYPH_CONFUSION")

    def test_feet_inches_and_decimal_degree_shapes_never_parse_as_coordinate(
            self):
        # Adversarial review finding (the original defect this session's
        # own new _COORD_RE regression-tests): making the degree symbol
        # optional between degrees and minutes let the regex engine
        # backtrack a plain digit run into an arbitrary, meaningless deg/
        # min split with no separator at all - "12'10\"N" (a feet-inches
        # measurement, not a coordinate) matched as deg=1/min=2, and
        # "20.41'18.46\"N" (a real target's ° misread as '.') matched as
        # deg=20.4/min=1 - both silently wrong, unflagged. Minutes are now
        # reachable ONLY through a literal degree symbol.
        for text in ("12'10\"N", "23'59\"W", "08'20.06\"N",
                     "20.41'18.46\"N", "49.5008'20.06\"N"):
            out = parse_coordinate(text)
            self.assertEqual(out.parse_status, "MALFORMED_NUMBER",
                             repr(text))
            self.assertIsNone(out.normalized_value, repr(text))

    def test_out_of_range_degrees_without_hemisphere_flagged(self):
        # No hemisphere letter -> widest bound (180) still catches this.
        out = parse_coordinate("200°00'00\"")
        self.assertEqual(out.parse_status, "SUSPECT_GLYPH_CONFUSION")

    def test_minutes_out_of_physical_range_flagged(self):
        out = parse_coordinate("49°70'20.06\"N")
        self.assertEqual(out.parse_status, "SUSPECT_GLYPH_CONFUSION")

    def test_seconds_out_of_physical_range_flagged(self):
        # degrees=49, minutes=08, seconds=70 - physically impossible.
        out = parse_coordinate("49°08'70.06\"N")
        self.assertEqual(out.parse_status, "SUSPECT_GLYPH_CONFUSION")

    def test_ascii_prime_and_double_quote_confusables_accepted(self):
        # A straight apostrophe/quote (what OCR usually emits) is accepted
        # alongside the true prime/double-prime typographic marks.
        out_ascii = parse_coordinate("49°08'20.06\"N")
        out_typographic = parse_coordinate("49°08′20.06″N")
        self.assertEqual(out_ascii.parse_status, "OK")
        self.assertEqual(out_typographic.parse_status, "OK")
        self.assertAlmostEqual(float(out_ascii.normalized_value),
                               float(out_typographic.normalized_value),
                               places=5)

    def test_double_prime_as_two_ascii_apostrophes_accepted(self):
        out = parse_coordinate("49°08'20.06''N")
        self.assertEqual(out.parse_status, "OK")

    def test_garbage_text_is_malformed_not_a_guess(self):
        out = parse_coordinate("abc")
        self.assertEqual(out.parse_status, "MALFORMED_NUMBER")

    def test_empty_text_is_no_number(self):
        out = parse_coordinate("")
        self.assertEqual(out.parse_status, "NO_NUMBER")

    def test_two_coordinates_in_one_string_never_silently_picks_one(self):
        # The full owner-reported overlay line (lat + long together) must
        # not be silently reduced to just one of the two values.
        out = parse_coordinate(
            "49008'20.06\"N 123003'41.61\"W")
        self.assertEqual(out.parse_status, "MALFORMED_NUMBER")
        self.assertIsNone(out.normalized_value)

    def test_replacement_character_from_failed_glyph_recognition_flagged(self):
        # A real S7-target repro this session: OCR sometimes emits U+FFFD
        # (the Unicode replacement character) rather than a digit for a
        # badly-recognized glyph. Must never be silently skipped over.
        out = parse_coordinate("49�08'20.06\"N")
        self.assertEqual(out.parse_status, "MALFORMED_NUMBER")

    def test_routed_through_parse_for_source_by_data_type(self):
        raw = bound_raw("49008'20.06\"N")
        out = parse_for_source(raw, "coordinate")
        self.assertEqual(out.parse_status, "OK")  # recovered, labelled
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)
        raw_ok = bound_raw("49°08'20.06\"N")
        out_ok = parse_for_source(raw_ok, "coordinate")
        self.assertEqual(out_ok.parse_status, "OK")
        self.assertNotIn("DEGREE_GLYPH_RECOVERED", out_ok.warning_codes)

    def test_coordinate_is_a_valid_data_type(self):
        self.assertIn("coordinate", C.DATA_TYPES)

    def test_suspect_glyph_confusion_is_a_retainable_error(self):
        self.assertIn("SUSPECT_GLYPH_CONFUSION",
                      C.RETAINABLE_ERROR_VALUE_STATUSES)

    def test_suspect_glyph_confusion_flows_through_derive_value_status(self):
        status = C.derive_value_status(
            "OK", "OK", "SUSPECT_GLYPH_CONFUSION", "NOT_EVALUATED")
        self.assertEqual(status, "SUSPECT_GLYPH_CONFUSION")


class LinePartParsingTests(unittest.TestCase):
    """Phase 2 (2026-07-19): the real target's readout is one thin overlay
    line holding lat+long+elev together, not three separately-drawable
    lines - measured evidence (M2_IMPLEMENTATION_REPORT.md §5k Phase 2.1)
    showed only ~5px of gap between adjacent values at realistic on-screen
    scale, too narrow to reliably draw three non-overlapping sub-regions by
    mouse. `line_part` lets several fields share ONE drawn region: each
    field parses only its own whitespace-separated token out of that
    region's OCR text, everything else about parsing (data_type, range,
    precision) is unchanged."""

    LINE = "49°08'20.06\"N 123°03'41.61\"W 87.05"

    def test_first_part_of_a_shared_line(self):
        raw = bound_raw(self.LINE)
        out = parse_for_source(raw, "coordinate", line_part=0)
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")

    def test_second_part_of_a_shared_line(self):
        raw = bound_raw(self.LINE)
        out = parse_for_source(raw, "coordinate", line_part=1)
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "-123.061558")

    def test_third_part_of_a_shared_line(self):
        raw = bound_raw(self.LINE)
        out = parse_for_source(raw, "number", line_part=2)
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "87.05")

    def test_out_of_range_part_index_is_no_number_not_a_crash(self):
        raw = bound_raw(self.LINE)
        out = parse_for_source(raw, "number", line_part=5)
        self.assertEqual(out.parse_status, "NO_NUMBER")
        self.assertIsNone(out.normalized_value)

    def test_out_of_range_part_never_reuses_a_neighbouring_token(self):
        # A field asking for a token that doesn't exist must never fall
        # back to the LAST token or any other token - that would silently
        # attribute one field's OCR text to a different field.
        raw = bound_raw("87.05")  # only one token, index 0
        out = parse_for_source(raw, "number", line_part=1)
        self.assertEqual(out.parse_status, "NO_NUMBER")

    def test_none_line_part_parses_the_whole_text_unaffected(self):
        # Default (None) behavior for a normal, single-value field must be
        # completely unchanged by this feature's existence.
        raw = bound_raw("87.05")
        with_none = parse_for_source(raw, "number", line_part=None)
        without_kw = parse_for_source(raw, "number")
        self.assertEqual(with_none.parse_status, without_kw.parse_status)
        self.assertEqual(with_none.normalized_value,
                         without_kw.normalized_value)

    def test_corrupted_token_within_a_shared_line_recovers_with_label(self):
        # Same corrupted-degree danger case as Phase 1, reached via a
        # line_part extraction - since 2026-07-21 the full-DMS shape
        # recovers to the numeric value, always labelled, never silent.
        raw = bound_raw("49008'20.06\"N 123°03'41.61\"W 87.05")
        out = parse_for_source(raw, "coordinate", line_part=0)
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)

    def test_extra_whitespace_between_tokens_does_not_shift_indices(self):
        # Extra whitespace BETWEEN two coordinates (not inside either one)
        # must still yield exactly two tokens - str.split() with no
        # argument collapses any run of whitespace.
        raw = bound_raw("49°08'20.06\"N   123°03'41.61\"W")
        out0 = parse_for_source(raw, "coordinate", line_part=0)
        out1 = parse_for_source(raw, "coordinate", line_part=1)
        self.assertEqual(out0.parse_status, "OK")
        self.assertEqual(out1.parse_status, "OK")


class LooksLikeCoordinateTests(unittest.TestCase):
    """A real owner (2026-07-19, after the coordinate type shipped) kept a
    field typed "number" and hit exactly the danger case it exists to
    catch - and the generic AMBIGUOUS_MULTIPLE_NUMBERS guidance ("redraw a
    tighter region") was actively wrong advice for it. This heuristic (UI
    hint only, never used to change a parsed value) detects that specific
    situation using the owner's own exact reported strings."""

    def test_real_owner_strings_detected(self):
        # Verbatim (minus the actual coordinates) from the owner's own
        # screenshots this session, including OCR's stray trailing glyph.
        cases = [
            "49008'21.81\"N �",
            "123003'31.57\"W",
            "49008'01.80\" N �",
            "123004'03.68\"W",
        ]
        for text in cases:
            self.assertTrue(looks_like_coordinate(text), repr(text))

    def test_correctly_read_degree_symbol_also_detected(self):
        self.assertTrue(looks_like_coordinate("49°08'20.06\"N"))

    def test_elevation_and_plain_numbers_never_flagged(self):
        for text in ("2 cm", "14 m", "660", "87.05", ""):
            self.assertFalse(looks_like_coordinate(text), repr(text))

    def test_unrelated_text_never_flagged(self):
        self.assertFalse(looks_like_coordinate("hello world"))


class ValueStatusGuidanceCoordinateHintTests(unittest.TestCase):
    """The context-aware override in ui.layout.value_status_guidance -
    tested here (not test_humanization.py) because it depends on
    looks_like_coordinate, this module's own function."""

    def test_number_type_with_coordinate_shaped_text_gets_specific_hint(self):
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "AMBIGUOUS_MULTIPLE_NUMBERS",
            raw_text="49008'21.81\"N �", data_type="number")
        self.assertIn("coordinate", text.lower())
        self.assertIn("Type", text)

    def test_coordinate_type_never_gets_the_hint_even_if_it_would_match(self):
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "MALFORMED_NUMBER", raw_text="49008'21.81\"N",
            data_type="coordinate")
        # A coordinate-typed field never shows AMBIGUOUS_MULTIPLE_NUMBERS
        # (parse_coordinate never returns it) - but MALFORMED_NUMBER can
        # still occur (e.g. garbage OCR); the hint must not fire for a
        # field ALREADY set to coordinate, since that would be circular
        # advice ("switch to coordinate" on a field already coordinate).
        self.assertNotIn("coordinate\"", text)

    def test_non_coordinate_shaped_text_keeps_the_generic_message(self):
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "AMBIGUOUS_MULTIPLE_NUMBERS", raw_text="12 34", data_type="number")
        self.assertIn("Redraw", text)

    def test_default_arguments_keep_existing_behavior(self):
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance("AMBIGUOUS_MULTIPLE_NUMBERS")
        self.assertIn("Redraw", text)


class LooksLikeAlphanumericCodeTests(unittest.TestCase):
    """Owner ask (2026-07-19, same session as the coordinate hint): the
    same "wrong type, wrong advice" class of problem generalized beyond
    coordinates to alphanumeric codes/serial numbers - e.g. "SN-4829" on a
    "number" field. Deliberately conservative: a clean number with a short
    trailing unit ("87.05m") or a label separated from a clean number by
    whitespace/":" ("Elevation: 87.05") must NOT be flagged - redrawing
    tighter around the value is still the right fix for those, and this
    heuristic must never compete with that correct, existing advice."""

    def test_genuine_codes_detected(self):
        for text in ("SN-4829", "A-12", "12A34", "Unit_88"):
            self.assertTrue(looks_like_alphanumeric_code(text), repr(text))

    def test_number_with_trailing_unit_never_flagged(self):
        for text in ("87.05m", "14 m", "2 cm", "5%"):
            self.assertFalse(looks_like_alphanumeric_code(text), repr(text))

    def test_label_prefix_with_clean_number_never_flagged(self):
        # The number itself is clean; a tighter redraw fixes this, not a
        # type change - the heuristic must not steer the owner wrong here.
        for text in ("Elevation: 87.05", "Cursor 49, 22", "Camera 205 m"):
            self.assertFalse(looks_like_alphanumeric_code(text), repr(text))

    def test_plain_numbers_and_pure_text_never_flagged(self):
        for text in ("660", "", "ABC", "hello world"):
            self.assertFalse(looks_like_alphanumeric_code(text), repr(text))

    def test_coordinate_shaped_text_never_double_flagged(self):
        # A real coordinate (even OCR-corrupted) must be handled by the
        # coordinate hint alone, never also flagged as a "code".
        self.assertFalse(looks_like_alphanumeric_code("49008'21.81\"N"))
        self.assertFalse(looks_like_alphanumeric_code("49°08'20.06\"N"))


class ValueStatusGuidanceAlphanumericHintTests(unittest.TestCase):
    def test_malformed_number_with_code_shaped_text_gets_specific_hint(self):
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "MALFORMED_NUMBER", raw_text="SN-4829", data_type="number")
        self.assertIn("letters", text.lower())
        self.assertIn("text", text)
        self.assertIn("auto", text)

    def test_no_number_with_any_letters_gets_specific_hint(self):
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "NO_NUMBER", raw_text="Unit Name", data_type="number")
        self.assertIn("text", text)
        self.assertIn("auto", text)

    def test_malformed_number_with_trailing_unit_keeps_generic_message(self):
        # "87.05m" is a clean number with a stray unit letter - redrawing
        # or checking the decimal separator is still the right advice,
        # never "switch to text".
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "MALFORMED_NUMBER", raw_text="87.05m", data_type="number")
        self.assertNotIn("text\"", text)
        self.assertIn("digits", text.lower())

    def test_no_number_with_no_letters_keeps_generic_message(self):
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "NO_NUMBER", raw_text="---", data_type="number")
        self.assertIn("Redraw", text)

    def test_text_typed_field_never_gets_this_hint(self):
        # A field already typed "text" would never actually reach
        # MALFORMED_NUMBER/NO_NUMBER (parse_text always succeeds), but the
        # guard is tested directly for defense in depth.
        from screen2xyz_m2.ui.layout import value_status_guidance
        text = value_status_guidance(
            "MALFORMED_NUMBER", raw_text="SN-4829", data_type="text")
        self.assertNotIn("letters", text.lower())


class AutoCoordinateAwarenessTests(unittest.TestCase):
    """Owner escalation (2026-07-21, competition deadline): "auto" is the
    universal type, so it must understand a lat/long reading too. A
    correctly-read coordinate parses to decimal degrees; a corrupted one
    is flagged SUSPECT_GLYPH_CONFUSION (safe, retained) - never a wrong
    number, never silently text when it is clearly coordinate-shaped."""

    def test_correct_degree_symbol_parses_to_decimal_degrees(self):
        out = parse_auto("49°08'20.06\"N")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")
        self.assertEqual(out.value_kind, "number")

    def test_owner_exact_current_targets(self):
        # Verbatim from the owner's 2026-07-21 Google Earth screenshots.
        lat = parse_auto("20°41'18.46\"N")
        lon = parse_auto("105°55'22.59\"E")
        self.assertEqual((lat.parse_status, lat.normalized_value),
                         ("OK", "20.688461"))
        self.assertEqual((lon.parse_status, lon.normalized_value),
                         ("OK", "105.922942"))

    def test_corrupted_degree_symbol_recovers_with_label(self):
        out = parse_auto("49008'20.06\"N")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)

    def test_trailing_ocr_noise_stripped_before_the_strict_parse(self):
        # A stray bullet/replacement glyph after the hemisphere letter is
        # mechanical OCR noise, not content - it must not demote a
        # coordinate-shaped reading all the way to text.
        out = parse_auto("49008'20.06\"N •")
        self.assertEqual(out.parse_status, "OK")
        self.assertEqual(out.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", out.warning_codes)
        out_ok = parse_auto("49°08'20.06\"N •")
        self.assertEqual(out_ok.parse_status, "OK")
        self.assertEqual(out_ok.normalized_value, "49.138906")

    def test_plain_numbers_and_text_behavior_unchanged(self):
        self.assertEqual(parse_auto("87.05").normalized_value, "87.05")
        self.assertEqual(parse_auto("87.05").value_kind, "number")
        self.assertEqual(parse_auto("SN-4829").value_kind, "text")
        self.assertEqual(parse_auto("12 34").value_kind, "text")

    def test_configured_numeric_range_applies_to_coordinate_values_too(self):
        # Adversarial review finding: parse_auto's own contract comment
        # promises range/precision are "surfaced, never masked" - this was
        # silently bypassed for the new coordinate branch.
        out = parse_auto("49°08'20.06\"N", numeric_range=(0.0, 10.0))
        self.assertEqual(out.parse_status, "OUT_OF_RANGE")
        in_range = parse_auto("49°08'20.06\"N", numeric_range=(0.0, 90.0))
        self.assertEqual(in_range.parse_status, "OK")

    def test_configured_precision_max_applies_to_coordinate_values_too(self):
        # A coordinate always formats 6 decimal places; a field configured
        # for fewer must reject it exactly like the number path does.
        out = parse_auto("49°08'20.06\"N", precision_max=2)
        self.assertEqual(out.parse_status, "MALFORMED_NUMBER")
        full_precision = parse_auto("49°08'20.06\"N", precision_max=6)
        self.assertEqual(full_precision.parse_status, "OK")

    def test_feet_inches_never_silently_parsed_as_a_coordinate(self):
        # Adversarial review finding: the original _COORD_RE let a plain
        # digit run backtrack into an arbitrary deg/min split with no
        # degree symbol at all - "12'10\"N" (feet-inches, not a
        # coordinate) used to become a confident, unflagged wrong NUMBER
        # (value_kind="number"). It must fall through to preserved text
        # instead - parse_text itself always reports OK (never fails),
        # so value_kind is the signal that matters, not parse_status.
        out = parse_auto("12'10\"N")
        self.assertEqual(out.value_kind, "text")
        self.assertEqual(out.normalized_value, "12'10\"N")


class SuggestFieldTypeTests(unittest.TestCase):
    """The pure decision function behind the Preview gate's one-click
    type-fix dialog (2026-07-21): given one field's real preview outcome,
    which type would actually work - or None when the current type is
    fine / redrawing genuinely is the right advice."""

    def test_coordinate_shaped_text_on_number_suggests_coordinate(self):
        from screen2xyz_m2.ui.layout import suggest_field_type
        for raw in ("49008'21.81\"N", "20°41'18.46\"N", "105°55'22.59\"E"):
            self.assertEqual(
                suggest_field_type(raw, "AMBIGUOUS_MULTIPLE_NUMBERS",
                                   "number"),
                "coordinate", repr(raw))

    def test_code_shaped_text_on_number_suggests_auto(self):
        from screen2xyz_m2.ui.layout import suggest_field_type
        self.assertEqual(
            suggest_field_type("SN-4829", "MALFORMED_NUMBER", "number"),
            "auto")

    def test_letters_only_no_number_suggests_auto(self):
        from screen2xyz_m2.ui.layout import suggest_field_type
        self.assertEqual(
            suggest_field_type("Unit Name", "NO_NUMBER", "number"), "auto")

    def test_healthy_field_never_gets_a_suggestion(self):
        from screen2xyz_m2.ui.layout import suggest_field_type
        self.assertIsNone(suggest_field_type("87.05", "OK", "number"))

    def test_genuine_two_numbers_keeps_redraw_advice(self):
        # "12 34" really is two numbers in one region - redrawing tighter
        # IS the right fix; a type switch would not help and must not be
        # offered.
        from screen2xyz_m2.ui.layout import suggest_field_type
        self.assertIsNone(
            suggest_field_type("12 34", "AMBIGUOUS_MULTIPLE_NUMBERS",
                               "number"))

    def test_already_coordinate_typed_never_resuggested(self):
        from screen2xyz_m2.ui.layout import suggest_field_type
        self.assertIsNone(
            suggest_field_type("49008'21.81\"N",
                               "AMBIGUOUS_MULTIPLE_NUMBERS", "coordinate"))

    def test_empty_text_never_suggests(self):
        from screen2xyz_m2.ui.layout import suggest_field_type
        self.assertIsNone(
            suggest_field_type("", "MALFORMED_NUMBER", "number"))
