from __future__ import annotations

import unittest

from screen2xyz_civil.pattern_edge import (
    MIN_REVERSALS,
    PatternEdgeError,
    edge_runs,
    flatten_to_envelope,
    oscillation_profile,
    pattern_chase_report,
)

# Synthetic geometry only. Each case reproduces the shape of a failure seen on
# a real sheet without carrying a coordinate from a proprietary drawing.
PITCH = 13.6  # a hatch stroke spacing, in points


def sawtooth(n, *, pitch=PITCH, low=100.0, high=106.4, x0=0.0):
    """A boundary chasing a hatch: alternating between two lines at the pitch."""
    pts = []
    for i in range(n):
        pts.append((x0 + i * pitch, low if i % 2 else high))
    return pts


def closed_band(top_run):
    """Close a run into a ring with a straight far side."""
    x0, x1 = top_run[0][0], top_run[-1][0]
    return top_run + [(x1, 60.0), (x0, 60.0)]


class OscillationTests(unittest.TestCase):
    def test_a_straight_edge_never_reverses(self):
        values = [100.0] * 10
        positions = [i * 10.0 for i in range(10)]
        profile = oscillation_profile(values, positions)
        self.assertEqual(profile["reversals"], 0)
        self.assertFalse(profile["regular"])

    def test_a_monotone_slope_never_reverses(self):
        values = [100.0 + i for i in range(10)]
        positions = [i * 10.0 for i in range(10)]
        self.assertEqual(oscillation_profile(values, positions)["reversals"], 0)

    def test_a_square_wave_reverses_at_a_regular_period(self):
        pts = sawtooth(14)
        profile = oscillation_profile([p[1] for p in pts], [p[0] for p in pts])
        self.assertGreaterEqual(profile["reversals"], MIN_REVERSALS)
        self.assertAlmostEqual(profile["period_pt"], PITCH, delta=1.0)
        self.assertAlmostEqual(profile["amplitude_pt"], 6.4, delta=0.1)
        self.assertTrue(profile["regular"])

    def test_one_irregular_kink_is_not_a_pattern(self):
        # A driveway throat or a curb return bends the edge once. That must not
        # read as pattern chasing.
        values = [100.0, 100.0, 100.0, 104.0, 108.0, 108.0, 108.0]
        positions = [i * 10.0 for i in range(7)]
        self.assertFalse(oscillation_profile(values, positions)["regular"])

    def test_mismatched_lengths_are_refused(self):
        with self.assertRaises(PatternEdgeError):
            oscillation_profile([1.0, 2.0], [0.0])


class ReportTests(unittest.TestCase):
    def test_a_pattern_chasing_boundary_is_reported(self):
        report = pattern_chase_report(closed_band(sawtooth(14)), pitch_pt=PITCH)
        self.assertTrue(report["chasing_pattern"])
        self.assertIn("pattern", report["detail"])
        self.assertEqual(report["repair"], "pattern_edge.flatten_to_envelope")

    def test_the_period_is_matched_against_a_supplied_pitch(self):
        report = pattern_chase_report(closed_band(sawtooth(14)), pitch_pt=PITCH)
        self.assertTrue(report["worst"]["matches_pitch"])
        self.assertIn("matching the pattern pitch", report["detail"])

    def test_a_boundary_from_the_drawing_is_not_reported(self):
        # What vector_fill produces: a handful of points, no oscillation.
        ring = [(0.0, 100.0), (200.0, 101.5), (400.0, 103.0), (400.0, 60.0), (0.0, 60.0)]
        report = pattern_chase_report(ring, pitch_pt=PITCH)
        self.assertFalse(report["chasing_pattern"])
        self.assertEqual(report["detail"], "")

    def test_metres_are_reported_when_a_scale_is_given(self):
        report = pattern_chase_report(closed_band(sawtooth(14)), pitch_pt=PITCH,
                                      metres_per_unit=0.0881944444444444)
        self.assertIn("m)", report["detail"])
        self.assertGreater(report["worst"]["amplitude_m"], 0.0)

    def test_a_degenerate_boundary_is_refused(self):
        with self.assertRaises(PatternEdgeError):
            pattern_chase_report([(0.0, 0.0), (1.0, 1.0)])

    def test_a_non_finite_coordinate_is_refused(self):
        with self.assertRaises(PatternEdgeError):
            pattern_chase_report([(0.0, 0.0), (1.0, float("inf")), (2.0, 0.0)])


class RepairTests(unittest.TestCase):
    def test_flattening_removes_the_oscillation(self):
        ring = closed_band(sawtooth(14))
        fixed = flatten_to_envelope(ring, keep="inner")
        self.assertEqual(fixed["runs_flattened"], 1)
        self.assertFalse(pattern_chase_report(fixed["ring"], pitch_pt=PITCH)["chasing_pattern"])

    def test_it_snaps_to_the_side_that_repeats(self):
        # One side constant to a hundredth, the other wandering: the constant
        # one is the drawn line the strokes are clipped against.
        run = []
        for i in range(14):
            if i % 2:
                run.append((i * PITCH, 100.0))  # repeats exactly: the drawn line
            else:
                run.append((i * PITCH, 106.0 if (i // 2) % 2 == 0 else 107.5))
        fixed = flatten_to_envelope(closed_band(run), keep="constant")
        self.assertEqual(fixed["runs_flattened"], 1)
        self.assertAlmostEqual(fixed["changes"][0]["snapped_to"], 100.0, places=6)
        self.assertEqual(fixed["changes"][0]["side"], "low")

    def test_both_sides_constant_is_a_scope_question_and_is_refused(self):
        # Not noise: the edge square-waves between two real drawn lines and
        # which one bounds the item is the drawing's answer, not a tolerance's.
        fixed = flatten_to_envelope(closed_band(sawtooth(14)), keep="constant")
        self.assertTrue(fixed["needs_a_scope_decision"])
        self.assertEqual(fixed["runs_flattened"], 0)
        run = fixed["ambiguous_runs"][0]
        self.assertAlmostEqual(run["separation_pt"], 6.4, places=6)
        self.assertIn("choose keep", run["reason"])

    def test_outer_and_inner_bracket_the_answer(self):
        ring = closed_band(sawtooth(14))
        outer = flatten_to_envelope(ring, keep="outer")["changes"][0]["snapped_to"]
        inner = flatten_to_envelope(ring, keep="inner")["changes"][0]["snapped_to"]
        self.assertGreater(outer, inner)
        self.assertAlmostEqual(outer - inner, 6.4, places=6)

    def test_a_corner_beyond_the_oscillation_is_left_alone(self):
        # The outline leaving the edge - a taper, a corner - must not be
        # dragged onto the snapped line. An earlier band of two full swings
        # pulled a corner vertex 30 pt.
        last_x = sawtooth(14)[-1][0]
        ring = closed_band(sawtooth(14) + [(last_x + 20.0, 140.0), (last_x + 40.0, 180.0)])
        fixed = flatten_to_envelope(ring, keep="inner")
        self.assertGreater(fixed["changes"][0]["points_left_alone"], 0)
        self.assertLessEqual(fixed["changes"][0]["moved_pt"], 7.0)

    def test_a_clean_boundary_is_returned_unchanged(self):
        ring = [(0.0, 100.0), (200.0, 101.5), (400.0, 103.0), (400.0, 60.0), (0.0, 60.0)]
        fixed = flatten_to_envelope(ring)
        self.assertEqual(fixed["runs_flattened"], 0)
        self.assertFalse(fixed["needs_a_scope_decision"])

    def test_an_unknown_keep_is_refused(self):
        with self.assertRaises(PatternEdgeError):
            flatten_to_envelope(closed_band(sawtooth(14)), keep="whatever")

    def test_the_input_ring_is_never_edited_in_place(self):
        ring = closed_band(sawtooth(14))
        before = [tuple(p) for p in ring]
        flatten_to_envelope(ring, keep="inner")
        self.assertEqual([tuple(p) for p in ring], before)


class EdgeRunTests(unittest.TestCase):
    def test_a_ring_is_split_where_it_turns_the_corner(self):
        ring = closed_band(sawtooth(14))
        runs = edge_runs(ring)
        self.assertTrue(runs)
        self.assertTrue(all(len(r) >= 5 for r in runs))

    def test_too_few_points_yields_no_runs(self):
        self.assertEqual(edge_runs([(0.0, 0.0), (1.0, 0.0)]), [])


if __name__ == "__main__":
    unittest.main()
