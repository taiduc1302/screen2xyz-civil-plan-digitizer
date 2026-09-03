import unittest

from screen2xyz_civil.vector_fill import (
    EdgeProfile,
    VectorFillError,
    band,
    colour_matches,
    crossings,
    edge_profile,
    markup_path,
    polyline_length,
    raster_trace_signature,
    raw_frame,
    shoelace_area,
    simplify,
)

PAGE_H = 1684.0


def slab(x0, x1, y0, y1):
    """A fill slab in the raw frame, the shape this drawing set emits."""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class RawFrameTests(unittest.TestCase):
    def test_y_flips_and_x_does_not(self):
        self.assertEqual(raw_frame([(100.0, 200.0)], PAGE_H), [(100.0, 1484.0)])

    def test_round_trip_is_its_own_inverse(self):
        once = raw_frame([(5.0, 7.0)], PAGE_H)
        self.assertEqual(raw_frame(once, PAGE_H), [(5.0, 7.0)])


class ColourTests(unittest.TestCase):
    def test_matches_within_tolerance(self):
        self.assertTrue(colour_matches((0.9019, 0.9019, 0.9019), (0.902, 0.902, 0.902)))

    def test_rejects_a_different_grey(self):
        self.assertFalse(colour_matches((0.502, 0.502, 0.502), (0.902, 0.902, 0.902)))

    def test_unfilled_path_is_not_a_match(self):
        self.assertFalse(colour_matches(None, (0.902, 0.902, 0.902)))


class CrossingTests(unittest.TestCase):
    def test_a_rectangle_is_crossed_twice(self):
        self.assertEqual(sorted(crossings(slab(0, 10, 0, 4), 5.0)), [0.0, 4.0])

    def test_outside_the_ring_there_are_no_crossings(self):
        self.assertEqual(crossings(slab(0, 10, 0, 4), 20.0), [])

    def test_vertical_edges_do_not_count_as_crossings(self):
        # the edge at x=0 is vertical; sampling exactly there must not double up
        self.assertEqual(len(crossings(slab(0, 10, 0, 4), 0.0)), 2)


class EdgeProfileTests(unittest.TestCase):
    def test_outer_extremes_ignore_an_interior_gap(self):
        # two slabs with a 3 pt gap between them, as the exporter emits a
        # corridor interrupted by a lane line
        rings = [slab(0, 100, 0, 10), slab(0, 100, 13, 20)]
        prof = edge_profile(rings, 10.0, 90.0, step=10.0)
        self.assertTrue(all(t == 0.0 for t in prof.top))
        self.assertTrue(all(b == 20.0 for b in prof.bottom))

    def test_refuses_an_empty_range(self):
        with self.assertRaises(VectorFillError):
            edge_profile([slab(0, 10, 0, 4)], 50.0, 60.0, step=1.0)

    def test_refuses_a_reversed_range(self):
        with self.assertRaises(VectorFillError):
            edge_profile([slab(0, 10, 0, 4)], 8.0, 2.0)

    def test_columns_stay_the_same_length(self):
        with self.assertRaises(VectorFillError):
            EdgeProfile([1.0, 2.0], [1.0], [2.0, 3.0])


class SimplifyTests(unittest.TestCase):
    def test_a_straight_run_collapses_to_its_ends(self):
        pts = [(float(i), 0.0) for i in range(20)]
        self.assertEqual(simplify(pts), [(0.0, 0.0), (19.0, 0.0)])

    def test_a_corner_survives_dense_sampling(self):
        # the crown case: neighbours are 0.001 apart, the corner must stay
        left = [(-100.0 + i * 0.001, 90.0) for i in range(50)]
        peak = [(0.0, 100.0)]
        right = [(0.001 * i, 90.0) for i in range(1, 50)]
        kept = simplify(left + peak + right, tolerance=0.3)
        self.assertIn((0.0, 100.0), kept)

    def test_tolerance_is_respected(self):
        pts = [(0.0, 0.0), (5.0, 0.4), (10.0, 0.0)]
        self.assertEqual(len(simplify(pts, tolerance=1.0)), 2)
        self.assertEqual(len(simplify(pts, tolerance=0.1)), 3)


class BandTests(unittest.TestCase):
    def test_band_between_two_chains_has_the_expected_area(self):
        upper = [(0.0, 0.0), (10.0, 0.0)]
        lower = [(0.0, 4.0), (10.0, 4.0)]
        ring = band(upper, lower)
        self.assertAlmostEqual(shoelace_area(ring), 40.0)

    def test_a_chain_of_one_point_is_refused(self):
        with self.assertRaises(VectorFillError):
            band([(0.0, 0.0)], [(0.0, 1.0), (1.0, 1.0)])


class MeasurementTests(unittest.TestCase):
    def test_polyline_length_of_a_straight_run(self):
        self.assertAlmostEqual(polyline_length([(0.0, 0.0), (3.0, 4.0)]), 5.0)

    def test_a_zigzag_is_longer_than_its_span(self):
        # the Sheet 04 shoulder defect: the same span, 2x the length
        span = [(0.0, 0.0), (40.0, 0.0)]
        zigzag = [(float(i), 0.0 if i % 2 else 10.0) for i in range(41)]
        self.assertGreater(polyline_length(zigzag), 2 * polyline_length(span))


class MarkupPathTests(unittest.TestCase):
    def test_closed_path_ends_with_H(self):
        path = markup_path(slab(0, 10, 0, 4))
        self.assertTrue(path.endswith(" H"))
        self.assertEqual(path.count("M"), 1)

    def test_open_path_has_no_H(self):
        path = markup_path([(0.0, 0.0), (10.0, 1.0)], closed=False)
        self.assertNotIn("H", path)

    def test_one_ring_only(self):
        # a Bluebeam polygon holds one ring; the host silently bridges two into
        # an invalid self-intersecting path, so the writer must never emit two
        path = markup_path(slab(0, 10, 0, 4))
        self.assertEqual(path.count("M"), 1)

    def test_refuses_a_degenerate_ring(self):
        with self.assertRaises(VectorFillError):
            markup_path([(1.0, 1.0), (1.0, 1.0)])


class SignatureTests(unittest.TestCase):
    def test_a_drawing_derived_boundary_does_not_look_traced(self):
        ring = [(0.0, 0.0), (500.0, 2.0), (500.0, 60.0), (0.0, 58.0)]
        self.assertEqual(raster_trace_signature(ring)["looks_raster_traced"], 0.0)

    def test_a_pixel_edge_trace_is_flagged(self):
        # 90 DPI pixel steps: many vertices, short axis-aligned segments
        ring = []
        for i in range(60):
            ring.append((i * 8.0, 0.0))
            ring.append((i * 8.0, 3.0))
        ring.append((480.0, 60.0))
        ring.append((0.0, 60.0))
        sig = raster_trace_signature(ring)
        self.assertEqual(sig["looks_raster_traced"], 1.0)
        self.assertGreater(sig["axis_aligned_fraction"], 0.5)

    def test_needs_three_points(self):
        with self.assertRaises(VectorFillError):
            raster_trace_signature([(0.0, 0.0), (1.0, 1.0)])


if __name__ == "__main__":
    unittest.main()
